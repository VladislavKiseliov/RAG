import uuid


class TaskDispatcherService:
    """Сервис, отвечающий за делегирование тяжелых задач в очередь."""

    def __init__(self, broker_client=None):
        self.broker = broker_client

    async def dispatch_ingestion(self, doc_id: uuid.UUID, minio_key: str):
        """Ставит задачу на обработку документа."""
        from rag_service.workers.task import ingest_document_task
        ingest_document_task.delay(str(doc_id), minio_key)

    async def dispatch_reindexing(self, doc_id: uuid.UUID):
        """Ставит задачу на переиндексацию (будущий метод)."""
        # from rag_service.workers.task import reindex_task
        # reindex_task.delay(str(doc_id))
        pass