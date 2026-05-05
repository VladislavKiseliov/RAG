# tasks.py

import uuid
import asyncio

from rag_service.api.schemas import DocumentStatus
from rag_service.celery_app import celery_app
from rag_service.infrastructure import  get_worker_container


# один loop на весь воркер
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)


@celery_app.task(name="ingest_document", bind=True, max_retries=3)
def ingest_document_task(self, doc_id: uuid.UUID, minio_key: str):
    # Получаем контейнер (создастся только один раз на процесс воркера)
    container = get_worker_container()

    async def _run():
        # Используем наш оркестратор/менеджер
        await container.ingestion_service.process_document(
            doc_id=doc_id,
            minio_key=minio_key,
        )

    try:
        _loop.run_until_complete(_run())
    except Exception as exc:
        # При ошибке обновляем статус через сервис из контейнера
        _loop.run_until_complete(
            container.document_service.update_document(
                doc_id=doc_id,
                status=DocumentStatus.ERROR,
            )
        )
        raise self.retry(exc=exc, countdown=60)