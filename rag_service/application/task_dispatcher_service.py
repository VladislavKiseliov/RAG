import logging
import uuid

from rag_service.api.schemas import DocumentStatus
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.domain.errors import DocumentByStorageKeyNotFound, DocumentNotFound
from rag_service.settings import settings

logger = logging.getLogger(__name__)


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


    async def dispatch_reindexing(self, doc_id: uuid.UUID) -> None:
        """Ставит задачу на полную переиндексацию уже загруженного документа.

        Переиспользует ту же Celery-таску, что и первичная загрузка (`ingest_document_task`) —
        `process_document` идемпотентен: сбрасывает главы/таблицы/parent chunks в Postgres
        (`reset_structural_data`) и старые векторы в Qdrant (`delete_by_field`) перед повторной
        обработкой. В отличие от `dispatch_ingestion` (webhook), здесь нет проверки на
        `status == PENDING` — реиндекс осмысленно вызывается именно для уже обработанного
        документа.
        """
        from rag_service.workers.task import ingest_document_task
        doc = await self.database.get_document_by_id(doc_id)
        if doc is None:
            raise DocumentNotFound(str(doc_id))

        ingest_document_task.delay(str(doc_id), doc.s3key)

    async def dispatch_summarization(self, doc_id: uuid.UUID) -> None:
        """Пересобрать саммари глав + документа отдельно от полной переиндексации.

        Та же таска, что и авто-триггер после ingest — идемпотентна (перезаписывает
        summary, не накапливает), поэтому безопасно звать вручную, если саммари не
        сформировалось с первого раза (например, llm_service был недоступен).
        """
        doc = await self.database.get_document_by_id(doc_id)
        if doc is None:
            raise DocumentNotFound(str(doc_id))

        if not settings.enable_document_summarization:
            logger.info(
                "Chapter summarization disabled (ENABLE_DOCUMENT_SUMMARIZATION=false), "
                "ignoring manual trigger doc_id=%s", doc_id,
            )
            return

        from rag_service.workers.task import summarize_document_chapters_task
        summarize_document_chapters_task.delay(str(doc_id))


