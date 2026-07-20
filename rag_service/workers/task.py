import asyncio
import logging
import uuid

import httpx

from rag_service.celery_app import celery_app
from rag_service.container import build_worker_infrastructure
from rag_service.settings import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="ingest_document", bind=True, max_retries=3)
def ingest_document_task(self, doc_id: str, s3key: str):
    logger.info("Celery received ingestion task doc_id=%s", doc_id)

    with asyncio.Runner() as runner:
        container = runner.run(build_worker_infrastructure())
        _doc_id = uuid.UUID(doc_id)
        try:
            runner.run(container.ingestion_service.process_document(doc_id=_doc_id, s3key=s3key))
        except Exception as exc:
            # process_document() уже сам обработал детерминированные и неизвестные
            # ошибки внутри (статус ERROR + заглушка отложенной очистки) — сюда
            # долетают только транзиентные инфраструктурные сбои (S3/Qdrant/БД),
            # которые имеет смысл ретраить.
            logger.warning("Transient ingestion error doc_id=%s, retrying: %s", doc_id, exc)
            raise self.retry(exc=exc, countdown=60)


def _notify_backend_index_complete(note_id: str, *, note_status: str, chunk_count: int | None = None) -> None:
    """Best-effort callback into backend so it can persist chunk_count/status on its note row.

    backend owns the notes table; rag_service only vectorizes, so completion has to be
    pushed back across the service boundary instead of written directly.
    """
    url = f"{settings.backend_internal_url}/internal/notes/{note_id}/index-complete"
    payload = {"status": note_status}
    if chunk_count is not None:
        payload["chunk_count"] = chunk_count
    try:
        httpx.Client(timeout=10.0).post(url, json=payload)
    except Exception:
        logger.exception("Failed to notify backend about note indexing result note_id=%s", note_id)


@celery_app.task(name="index_note", bind=True, max_retries=3)
def index_note_task(self, note_id: str, user_id: str, text: str):
    logger.info("Celery received note indexing task note_id=%s", note_id)

    from rag_service.application.note_vectorization_service import NoteVectorizationService

    with asyncio.Runner() as runner:
        container = runner.run(build_worker_infrastructure())
        service = NoteVectorizationService(
            vector_storage=container.notes_vector_storage,
            vector_indexing_service=container.v_indexing_service,
        )
        try:
            chunk_count = runner.run(service.index_note(uuid.UUID(note_id), user_id, text))
        except Exception as exc:
            logger.warning("Transient note indexing error note_id=%s, retrying: %s", note_id, exc)
            _notify_backend_index_complete(note_id, note_status="error")
            raise self.retry(exc=exc, countdown=30)

    _notify_backend_index_complete(note_id, note_status="indexed", chunk_count=chunk_count)