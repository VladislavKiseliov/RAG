import uuid

from rag_service.api.schemas import DocumentStatus
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.domain.errors import DocumentByStorageKeyNotFound, DocumentNotFound


class TaskDispatcherService:
    """Сервис, отвечающий за делегирование тяжелых задач в очередь."""

    def __init__(self, database:DataBaseDocumentService):
        self.database = database

    async def dispatch_ingestion(self, s3key: str) -> None:
        """Ставит задачу на обработку документа.

        Идемпотентно: MinIO доставляет вебхуки at-least-once, а `handle_webhook` возвращает
        200 даже если часть записей батча упала (см. per-record try/except там) — то есть один
        и тот же s3key может прилететь сюда повторно. Документ уже не в PENDING значит уже
        задиспатчен/обрабатывается/готов — повторный `.delay()` создал бы гонку с уже идущим
        `ingest_document_task` (см. B6 в ISSUES.md).
        """
        from rag_service.workers.task import ingest_document_task
        doc = await self.database.get_document_by_s3key(s3key)
        if doc is None:
            raise DocumentByStorageKeyNotFound(s3key)

        if doc.status != DocumentStatus.PENDING:
            return

        await self.database.update_document(doc.id, update_data={"status": DocumentStatus.UPLOAD})
        ingest_document_task.delay(str(doc.id), s3key)


    async def dispatch_reindexing(self, doc_id: uuid.UUID):
        """Ставит задачу на переиндексацию (будущий метод)."""
        # from rag_service.workers.task import reindex_task
        # reindex_task.delay(str(doc_id))
        pass

    async def dispatch_summarization(self, doc_id: uuid.UUID) -> None:
        """Пересобрать саммари глав + документа отдельно от полной переиндексации.

        Та же таска, что и авто-триггер после ingest — идемпотентна (перезаписывает
        summary, не накапливает), поэтому безопасно звать вручную, если саммари не
        сформировалось с первого раза (например, llm_service был недоступен).
        """
        from rag_service.workers.task import summarize_document_chapters_task
        doc = await self.database.get_document_by_id(doc_id)
        if doc is None:
            raise DocumentNotFound(str(doc_id))

        summarize_document_chapters_task.delay(str(doc_id))


