import uuid
from datetime import datetime
from typing import Protocol, Any, Iterable, runtime_checkable


@runtime_checkable
class DocumentRepositoryProvider(Protocol):
    """
    Протокол для работы с документами и их родительскими чанками в SQL.

    Обеспечивает управление жизненным циклом документа:
    регистрация, поиск по хешу, пагинация и массовая вставка чанков.
    """

    async def get_document_by_hash(self, file_hash: str) -> Any | None:
        """Найти документ по SHA-256 хешу."""
        ...

    async def get_document_by_id(self, doc_id: uuid.UUID) -> Any | None:
        """Найти документ по его UUID."""
        ...

    async def list_documents(
            self,
            *,
            limit: int,
            offset: int,
            status: str | None = None,
            filename: str | None = None,
            created_from: datetime | None = None,
            created_to: datetime | None = None,
    ) -> list[Any]:
        """Получить список документов с фильтрацией и пагинацией."""
        ...

    async def create_document(
            self,
            filename: str,
            metadata: dict | None,
            doc_status: Any,  # DocumentStatus enum
            doc_id: uuid.UUID | None = None,
            file_size: int | None = None,
    ) -> uuid.UUID:
        """Создать новую запись о документе."""
        ...

    async def set_status(
            self,
            doc_id: uuid.UUID,
            status: Any,  # DocumentStatus enum
            *,
            chunk_count: int | None = None,
    ) -> None:
        """Обновить статус документа и количество обработанных чанков."""
        ...

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        """Удалить документ из базы данных."""
        ...

    async def get_max_chunk_index(self, doc_id: uuid.UUID) -> int | None:
        """Получить индекс последнего чанка документа (для последовательности)."""
        ...

    async def get_parents_by_ids(
            self,
            parent_ids: list[uuid.UUID],
            *,
            doc_id: uuid.UUID | None = None,
    ) -> list[Any]:
        """Получить список родительских чанков по их ID."""
        ...

    async def bulk_insert_chunks(
            self,
            doc_id: uuid.UUID,
            chunks: Iterable[dict],
            *,
            batch_size: int | None = None,
            max_retries: int = 3,
    ) -> None:
        """
        Массовая вставка чанков в базу.
        Должна поддерживать обработку дедлоков и автоматический батчинг.
        """
        ...