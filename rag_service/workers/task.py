import asyncio
import logging
import uuid

from rag_service.celery_app import celery_app
from rag_service.container import build_worker_infrastructure

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