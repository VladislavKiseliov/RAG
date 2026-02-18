from __future__ import annotations

import asyncio
import uuid
from typing import Iterable

import asyncpg
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.sql import Select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from rag_service.core.exceptions import DocumentAlreadyExists, DocumentNotFound
from rag_service.models import DocumentStatus, Documents, ParentChunks


class DocumentRepository:
    """Инкапсулирует SQL-операции для схемы rag_kernel.

    ВАЖНО:
    - Все операции выполняются через AsyncSession.
    - Коммит/роллбек остаются на уровне оркестрации (сервис/внешний слой).
    - Репозиторий не обращается к другим схемам.
    """
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_document_by_hash(self, file_hash: str) -> Documents | None:
        """Возвращает документ по SHA-256 хэшу или None."""
        result = await self._session.execute(
            select(Documents).where(Documents.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def get_document_by_id(self, doc_id: uuid.UUID) -> Documents | None:
        """Возвращает документ по UUID или None."""
        result = await self._session.execute(
            select(Documents).where(Documents.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        *,
        limit: int,
        offset: int,
        status: str | None = None,
        filename: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[Documents]:
        """Возвращает список документов с пагинацией и фильтрами."""
        query: Select = select(Documents)

        if status:
            query = query.where(Documents.status == status)
        if filename:
            query = query.where(Documents.filename.ilike(f"%{filename}%"))
        if created_from:
            query = query.where(Documents.created_at >= created_from)
        if created_to:
            query = query.where(Documents.created_at <= created_to)

        query = query.order_by(Documents.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def create_doc(
        self,
        filename: str,
        file_hash: str,
        meta: dict | None,
        *,
        doc_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Создает документ со статусом processing и делает flush для получения UUID.

        При гонке по уникальности file_hash переводит IntegrityError в DocumentAlreadyExists.
        """
        doc = Documents(
            id=doc_id or uuid.uuid4(),
            filename=filename,
            file_hash=file_hash,
            meta=meta,
            status=DocumentStatus.processing,
        )
        self._session.add(doc)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            if isinstance(exc.orig, asyncpg.exceptions.UniqueViolationError):
                constraint = exc.orig.constraint_name or ""
                if constraint == "uq_documents_file_hash" or "file_hash" in constraint:
                    raise DocumentAlreadyExists(file_hash) from exc
            raise
        return doc.id

    async def set_status(self, doc_id: uuid.UUID, status: DocumentStatus) -> None:
        """Обновляет статус документа (completed/error)."""
        await self._session.execute(
            update(Documents)
            .where(Documents.id == doc_id)
            .values(status=status)
        )

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        """Удаляет документ. Чанки удаляются через ON DELETE CASCADE."""
        await self._session.execute(delete(Documents).where(Documents.id == doc_id))

    async def get_full_text(self, doc_id: uuid.UUID) -> str:
        """Собирает полный текст документа по chunk_index.

        Если чанков нет и документа не существует — поднимает DocumentNotFound.
        """
        result = await self._session.execute(
            select(ParentChunks.content)
            .where(ParentChunks.doc_id == doc_id)
            .order_by(ParentChunks.chunk_index.asc())
        )
        parts = [row[0] for row in result.all()]
        if not parts:
            doc = await self.get_document_by_id(doc_id)
            if doc is None:
                raise DocumentNotFound(str(doc_id))
        return "\n".join(parts)

    async def get_max_chunk_index(self, doc_id: uuid.UUID) -> int | None:
        """Возвращает максимальный chunk_index для документа (или None)."""
        result = await self._session.execute(
            select(func.max(ParentChunks.chunk_index)).where(ParentChunks.doc_id == doc_id)
        )
        return result.scalar_one()

    async def bulk_insert_chunks(
        self,
        doc_id: uuid.UUID,
        chunks: Iterable[dict],
        *, 
        batch_size: int | None = None,
        max_retries: int = 3,
    ) -> None:
        """Массовая вставка чанков с ретраями по deadlock.

        Требования:
        - Мультистрочный INSERT (без одиночных инсёртов).
        - Если чанков > 1000, вставка батчами 500–1000 записей.
        - При DeadlockDetectedError повторяем через 0.5 сек.
        """
        chunk_list = list(chunks)
        if not chunk_list:
            return

        if batch_size is None:
            batch_size = 1000 if len(chunk_list) <= 1000 else 500
        batch_size = max(500, min(1000, batch_size)) if len(chunk_list) > 1000 else batch_size

        def _prepare_rows(rows: list[dict]) -> list[dict]:
            prepared: list[dict] = []
            for row in rows:
                prepared.append(
                    {
                        "id": row.get("id", uuid.uuid4()),
                        "doc_id": doc_id,
                        "content": row["content"],
                        "chunk_index": row["chunk_index"],
                    }
                )
            return prepared

        for start in range(0, len(chunk_list), batch_size):
            batch = _prepare_rows(chunk_list[start : start + batch_size])
            attempts = 0
            while True:
                try:
                    await self._session.execute(insert(ParentChunks), batch)
                    break
                except DBAPIError as exc:
                    if isinstance(exc.orig, asyncpg.exceptions.DeadlockDetectedError):
                        attempts += 1
                        if attempts > max_retries:
                            raise
                        await asyncio.sleep(0.5)
                        continue
                    raise
