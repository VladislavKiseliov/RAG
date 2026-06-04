import asyncio
import logging
import uuid

from celery.exceptions import MaxRetriesExceededError, Retry

from rag_service.api.schemas import DocumentStatus
from rag_service.celery_app import celery_app
from rag_service.domain.errors.vector import VectorUpsertError, VectorCollectionError
from rag_service.infrastructure import build_worker_infrastructure

logger = logging.getLogger(__name__)


@celery_app.task(name="ingest_document", bind=True, max_retries=3)
def ingest_document_task(self, doc_id: str, s3key: str):
    logger.info("Celery received ingestion task doc_id=%s", doc_id)


    with asyncio.Runner() as runner:
        container = build_worker_infrastructure()
        _doc_id = uuid.UUID(doc_id)
        try:
            runner.run(container.ingestion_service.process_document(doc_id=_doc_id, s3key=s3key))

        except Exception as exc:
            # Фатальная ошибка — не ретраим
            logger.exception("Fatal ingestion error doc_id=%s", doc_id)
            runner.run(container.document_service.update_document(_doc_id, status=DocumentStatus.ERROR))

            raise exc