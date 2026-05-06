import uuid

from rag_service.api.schemas import DocumentStatus
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.domain.errors import DocumentByStorageKeyNotFound


class TaskDispatcherService:
    """Сервис, отвечающий за делегирование тяжелых задач в очередь."""

    def __init__(self, database:DataBaseDocumentService, broker_client=None):
        self.broker = broker_client
        self.database = database

    async def dispatch_ingestion(self, s3key: str) -> None:
        """Ставит задачу на обработку документа."""
        from rag_service.workers.task import ingest_document_task
        doc = await self.database.get_document_by_s3key(s3key)
        if doc is None:
            raise DocumentByStorageKeyNotFound(s3key)

        await self.database.update_document(doc_id=doc.id, status=DocumentStatus.UPLOAD)
        ingest_document_task.delay(str(doc.id), s3key)


    async def dispatch_reindexing(self, doc_id: uuid.UUID):
        """Ставит задачу на переиндексацию (будущий метод)."""
        # from rag_service.workers.task import reindex_task
        # reindex_task.delay(str(doc_id))
        pass


