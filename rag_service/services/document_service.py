from __future__ import annotations

import uuid
from pathlib import PurePath

from sqlalchemy.ext.asyncio import AsyncSession

from rag_service.models import DocumentStatus
from rag_service.repositories.document_repository import DocumentRepository


def _sanitize_filename(filename: str) -> str:
    """Удаляет пути и запрещенные сегменты из имени файла.

    Примеры:
    - "../../secret.txt" -> "secret.txt"
    - "C:\\tmp\\file.pdf" -> "file.pdf"
    """
    cleaned = filename.replace("\x00", "").replace("\\", "/")
    cleaned = cleaned.split("/")[-1]
    cleaned = cleaned.strip()
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("Invalid filename")
    # Avoid reserved path segments
    return PurePath(cleaned).name


class DocumentService:
    """Оркестрация RAG-операций на уровне БД.

    ВАЖНО:
    - Здесь не выполняется commit/rollback (синхронизация с векторным хранилищем).
    - Логика дедупликации и статусов хранится здесь, SQL — в репозитории.
    """
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = DocumentRepository(session)

    async def get_document_by_hash(self, file_hash: str):
        """Публичный метод проверки наличия документа по хэшу."""
        return await self._repo.get_document_by_hash(file_hash)

    async def create_doc(
        self,
        filename: str,
        file_hash: str,
        meta: dict | None = None,
        *,
        doc_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Создает документ с дедупликацией.

        Поведение:
        - completed -> возвращает существующий id
        - error -> удаляет запись и создает новую
        - processing -> возвращает существующий id
        """
        safe_name = _sanitize_filename(filename)
        existing = await self._repo.get_document_by_hash(file_hash)
        if existing is not None:
            if existing.status == DocumentStatus.completed:
                return existing.id
            if existing.status == DocumentStatus.error:
                await self._repo.delete_document(existing.id)
                await self._session.flush()
            else:
                return existing.id

        doc_id = await self._repo.create_doc(safe_name, file_hash, meta, doc_id=doc_id)
        return doc_id

    async def add_chunks(self, doc_id: uuid.UUID, contents: list[str]) -> None:
        """Добавляет чанки с автонумерацией chunk_index."""
        if not contents:
            return
        current_max = await self._repo.get_max_chunk_index(doc_id)
        start_index = (current_max + 1) if current_max is not None else 0
        chunks = [
            {"content": content, "chunk_index": start_index + idx}
            for idx, content in enumerate(contents)
        ]
        await self._repo.bulk_insert_chunks(doc_id, chunks)

    async def set_status(self, doc_id: uuid.UUID, status: DocumentStatus) -> None:
        """Переводит документ в completed/error."""
        await self._repo.set_status(doc_id, status)

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        """Удаляет документ и все чанки через CASCADE."""
        await self._repo.delete_document(doc_id)

    async def get_full_text(self, doc_id: uuid.UUID) -> str:
        """Возвращает полный текст документа, собранный по порядку chunk_index."""
        return await self._repo.get_full_text(doc_id)
