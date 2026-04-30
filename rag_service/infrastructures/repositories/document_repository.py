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

from rag_service.models import DocumentStatus, Documents, ParentChunks


class DocumentRepository:
    """Data access for `rag_kernel.documents` and `rag_kernel.parent_chunks`."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind repository to an active async SQLAlchemy session."""
        self._session = session

    async def get_document_by_hash(self, file_hash: str) -> Documents | None:
        """Return a document by SHA-256 hash, or `None` if absent."""
        result = await self._session.execute(
            select(Documents).where(Documents.file_hash == file_hash)
        )
        return result.scalar_one_or_none()

    async def get_document_by_id(self, doc_id: uuid.UUID) -> Documents | None:
        """Return a document by UUID, or `None` if absent."""
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
            created_from: datetime | None = None,
            created_to: datetime | None = None,
    ) -> list[Documents]:
        """List documents with pagination and optional filters."""
        query: Select = select(Documents)

        if status:
            query = query.where(Documents.status == status)
        if filename:
            query = query.where(Documents.filename.ilike(f"%{filename}%"))
        if created_from is not None:
            query = query.where(Documents.created_at >= created_from)
        if created_to is not None:
            query = query.where(Documents.created_at <= created_to)

        query = query.order_by(Documents.created_at.desc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def create_document(
            self,
            filename: str,
            metadata: dict | None,
            minio_key: str | None,
            doc_status: DocumentStatus,
            doc_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Create a document in `processing` status."""
        doc = Documents(
            id=doc_id,
            filename=filename,
            meta=metadata,
            minio_key=minio_key,
            status=doc_status,
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
        """Update document status and optionally its processed child chunk count."""
        values: dict[str, Any] = {"status": status}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count

        await self._session.execute(
            update(Documents).where(Documents.id == doc_id).values(**values)
        )

    async def update_document(
            self,
            doc_id: uuid.UUID,
            *,
            status: str | DocumentStatus | None = None,
            metadata: dict | None = None,
            chunk_count: int | None = None,
            minio_key: str | None = None,
            file_hash: str | None = None,
    ) -> None:
        """Update selected document fields by id."""
        values: dict[str, Any] = {}

        if status is not None:
            values["status"] = getattr(status, "value", status)
        if metadata is not None:
            values["meta"] = metadata
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if minio_key is not None:
            values["minio_key"] = minio_key
        if file_hash is not None:
            values["file_hash"] = file_hash

        if not values:
            return

        await self._session.execute(
            update(Documents).where(Documents.id == doc_id).values(**values)
        )

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        """Delete document row."""
        await self._session.execute(delete(Documents).where(Documents.id == doc_id))

    async def get_max_chunk_index(self, doc_id: uuid.UUID) -> int | None:
        """Return maximum parent chunk index for a document."""
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
        """Return parent chunks by id list."""
        if not parent_ids:
            return []

        query = select(ParentChunks).where(ParentChunks.id.in_(parent_ids))
        if doc_id is not None:
            query = query.where(ParentChunks.doc_id == doc_id)
        query = query.order_by(ParentChunks.chunk_index.asc())

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_parent_chunks_by_doc_id(self, doc_id: uuid.UUID) -> list[ParentChunks]:
        """Return all parent chunks for a document ordered by chunk_index."""
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
        """Bulk insert chunks with retry on deadlocks, using the shared session."""
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
