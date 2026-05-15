"""Repository layer for rag document and parent chunk persistence."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Iterable, Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from rag_service.models import DocumentStatus, DocumentListItemDTO, ParentChunks


class DocumentRepository:
    """Data access for `rag_kernel.documents` and `rag_kernel.parent_chunks`.

    The repository does not manage transaction boundaries. Callers are expected
    to commit or roll back using the owning SQLAlchemy session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind repository to an active async SQLAlchemy session.

        Args:
            session: Open async session used for all DB operations.
        """
        self._session = session

    async def update_document_hash_atomically(self, doc_id: uuid.UUID, file_hash: str, status: str) -> bool:
        """
            Executes an atomic SQL UPDATE to set the file hash and status.

            This method does not handle transaction commits or integrity exceptions;
            it relies on the database-level UNIQUE constraint ('uq_documents_file_hash')
            to prevent duplicate files.

            Args:
                doc_id: The unique identifier of the document to update.
                file_hash: SHA-256 hash of the document content.
                status: The new status to set (e.g., 'extracting').

            Raises:
                sqlalchemy.exc.SQLAlchemyError: If the database operation fails.
            """

        stmt = (
            update(DocumentListItemDTO)
            .where(DocumentListItemDTO.id == doc_id)
            .values(file_hash=file_hash, status=status)
        )
        await self._session.execute(stmt)



    async def _get_one(self, where_clause: Any) -> DocumentListItemDTO | None:
        """Return a single document row for the provided SQLAlchemy predicate.

        Args:
            where_clause: SQLAlchemy boolean expression for `WHERE`.

        Returns:
            Matching document row or `None` when no row matches.
        """
        result = await self._session.execute(
            select(DocumentListItemDTO).where(where_clause)
        )
        return result.scalar_one_or_none()

    async def get_document_by_s3key(self, s3key: str) -> DocumentListItemDTO | None:
        """Return a single document by its storage key.

        Args:
            s3key: Object key from storage (`documents.s3key`).

        Returns:
            Document row if found, otherwise `None`.
        """
        return await self._get_one(DocumentListItemDTO.s3key == s3key)

    async def get_document_by_hash(self, file_hash: str) -> DocumentListItemDTO | None:
        """Return a single document by its file hash.

        Args:
            file_hash: SHA-256 hash value stored in `documents.file_hash`.

        Returns:
            Document row if found, otherwise `None`.
        """
        return await self._get_one(DocumentListItemDTO.file_hash == file_hash)

    async def get_document_by_id(self, doc_id: uuid.UUID) -> DocumentListItemDTO | None:
        """Return a single document by its primary key.

        Args:
            doc_id: Document UUID.

        Returns:
            Document row if found, otherwise `None`.
        """
        return await self._get_one(DocumentListItemDTO.id == doc_id)

    async def list_documents(
            self,
            *,
            limit: int,
            offset: int,
            status: str | None = None,
            filename: str | None = None,
            created_from: datetime | None = None,
            created_to: datetime | None = None,
    ) -> list[DocumentListItemDTO]:
        """List documents using pagination and optional filters.

        Args:
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.
            status: Optional status filter.
            filename: Optional case-insensitive substring for filename search.
            created_from: Optional lower bound for creation timestamp.
            created_to: Optional upper bound for creation timestamp.

        Returns:
            Ordered list of matching documents (newest first).
        """
        query: Select = select(DocumentListItemDTO)

        if status:
            query = query.where(DocumentListItemDTO.status == status)
        if filename:
            query = query.where(DocumentListItemDTO.filename.ilike(f"%{filename}%"))
        if created_from is not None:
            query = query.where(DocumentListItemDTO.created_at >= created_from)
        if created_to is not None:
            query = query.where(DocumentListItemDTO.created_at <= created_to)

        query = query.order_by(DocumentListItemDTO.created_at.desc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def create_document(
            self,
            filename: str,
            metadata: dict | None,
            s3key: str | None,
            doc_status: DocumentStatus,
            doc_id: uuid.UUID | None = None,
            file_size: int | None = None,
    ) -> uuid.UUID:
        """Insert a new document row.

        Args:
            filename: Stored filename.
            metadata: JSON metadata to persist in `meta`.
            s3key: Object storage key for the uploaded file.
            doc_status: Initial document status.
            doc_id: Optional explicit UUID. If omitted, model default is used.

        Returns:
            UUID of the inserted document.
        """
        doc = DocumentListItemDTO(
            id=doc_id,
            filename=filename,
            meta=metadata,
            s3key=s3key,
            status=doc_status,
            file_size=file_size,
        )

        self._session.add(doc)
        await self._session.flush()

        return doc.id

    async def set_status(
            self,
            doc_id: uuid.UUID,
            status: DocumentStatus,
            *,
            chunk_count: int | None = None,
    ) -> None:
        """Update document status and optional chunk count.

        Args:
            doc_id: Target document UUID.
            status: New document status.
            chunk_count: Optional processed chunk count to persist.
        """
        values: dict[str, Any] = {"status": status}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count

        await self._session.execute(
            update(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id).values(**values)
        )

    async def update_document(
            self,
            doc_id: uuid.UUID,
            *,
            status: str | DocumentStatus | None = None,
            metadata: dict | None = None,
            chunk_count: int | None = None,
            s3key: str | None = None,
            file_hash: str | None = None,
    ) -> None:
        """Partially update selected document fields by id.

        Args:
            doc_id: Target document UUID.
            status: Optional status value.
            metadata: Optional metadata replacement for `meta`.
            chunk_count: Optional chunk count replacement.
            s3key: Optional object key replacement.
            file_hash: Optional file hash replacement.

        Notes:
            If all optional fields are `None`, the method exits without SQL.
        """
        values: dict[str, Any] = {}

        if status is not None:
            values["status"] = getattr(status, "value", status)
        if metadata is not None:
            values["meta"] = metadata
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if s3key is not None:
            values["s3key"] = s3key
        if file_hash is not None:
            values["file_hash"] = file_hash

        if not values:
            return

        await self._session.execute(
            update(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id).values(**values)
        )

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        """Delete a document row by id.

        Args:
            doc_id: Target document UUID.
        """
        await self._session.execute(delete(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id))

    async def get_max_chunk_index(self, doc_id: uuid.UUID) -> int | None:
        """Return the largest `chunk_index` for the document.

        Args:
            doc_id: Target document UUID.

        Returns:
            Maximum chunk index, or `None` when the document has no chunks.
        """
        result = await self._session.execute(
            select(func.max(ParentChunks.chunk_index)).where(ParentChunks.doc_id == doc_id)
        )
        return result.scalar_one()

    async def get_parents_by_ids(
            self,
            parent_ids: list[uuid.UUID],
            *,
            doc_id: uuid.UUID | None = None,
    ) -> list[ParentChunks]:
        """Return parent chunk rows by ids, optionally scoped to one document.

        Args:
            parent_ids: Parent chunk UUIDs to fetch.
            doc_id: Optional document UUID filter.

        Returns:
            Parent chunks ordered by `chunk_index` ascending.
        """
        if not parent_ids:
            return []

        query = select(ParentChunks).where(ParentChunks.id.in_(parent_ids))
        if doc_id is not None:
            query = query.where(ParentChunks.doc_id == doc_id)
        query = query.order_by(ParentChunks.chunk_index.asc())

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_parent_chunks_by_doc_id(self, doc_id: uuid.UUID) -> list[ParentChunks]:
        """Return all parent chunks for one document.

        Args:
            doc_id: Target document UUID.

        Returns:
            Parent chunks ordered by `chunk_index` ascending.
        """
        result = await self._session.execute(
            select(ParentChunks)
            .where(ParentChunks.doc_id == doc_id)
            .order_by(ParentChunks.chunk_index.asc())
        )
        return list(result.scalars().all())

    async def bulk_insert_chunks(
            self,
            doc_id: uuid.UUID,
            chunks: Iterable[dict],
            *,
            batch_size: int | None = None,
            max_retries: int = 3,
    ) -> None:
        """Bulk insert parent chunks with deadlock retry.

        Args:
            doc_id: Target document UUID used for all inserted rows.
            chunks: Iterable of chunk dictionaries with content and chunk_index.
            batch_size: Optional insert batch size. If omitted, auto-selected.
            max_retries: Number of retries for PostgreSQL deadlock (`40P01`).

        Notes:
            This method retries only deadlocks. Other DB errors are raised as-is.
        """
        chunk_list = list(chunks)
        if not chunk_list:
            return

        # Настройка батчинга
        if batch_size is None:
            batch_size = 1000 if len(chunk_list) <= 1000 else 500
        batch_size = max(500, min(1000, batch_size)) if len(chunk_list) > 1000 else batch_size

        def _prepare_rows(rows: list[dict]) -> list[dict]:
            return [
                {
                    "id": row.get("id", uuid.uuid4()),
                    "doc_id": doc_id,
                    "content": str(row["content"]),
                    "page_num": str(row.get("page_num") or ""),
                    "headers": row.get("headers") or {},
                    "chunk_index": row["chunk_index"],
                }
                for row in rows
            ]

        for start in range(0, len(chunk_list), batch_size):
            batch = _prepare_rows(chunk_list[start: start + batch_size])
            attempts = 0
            while True:
                try:
                    await self._session.execute(insert(ParentChunks), batch)
                    break
                except DBAPIError as exc:
                    # Обработка дедлока PostgreSQL (40P01)
                    if getattr(exc.orig, "sqlstate", None) == "40P01":
                        attempts += 1
                        if attempts > max_retries:
                            raise
                        await asyncio.sleep(0.5)
                        continue
                    raise
