# tasks.py
import os
import tempfile
import uuid
import asyncio

from rag_service.celery_app import celery_app
from rag_service.infrastructure import build_worker_infrastructure


container = build_worker_infrastructure()
ingestion_service = container.ingestion_service
minio_provider = container.minio_provider

# один loop на весь воркер
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)


@celery_app.task(name="ingest_document", bind=True, max_retries=3)
def ingest_document_task(self, doc_id: str, minio_key: str, filename: str):
    async def _run():
        tmp_path = None
        try:
            content = await minio_provider.download(minio_key)
            suffix = os.path.splitext(filename)[-1] or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            await ingestion_service.ingest_path(
                tmp_path,
                doc_id=uuid.UUID(doc_id),
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    try:
        _loop.run_until_complete(_run())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)