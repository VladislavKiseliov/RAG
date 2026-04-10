"""Service layer for document metadata and parent chunk persistence."""

from __future__ import annotations

import uuid
from pathlib import PurePath
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_service.infrastructures.repositories.document_repository import DocumentRepository
from rag_service.models import DocumentStatus, Documents, ParentChunks


def _sanitize_filename(filename: str) -> str:
    """Normalize uploaded filename and strip path traversal segments."""
    cleaned = filename.replace("\x00", "").replace("\\", "/")
    cleaned = cleaned.split("/")[-1].strip()
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("Invalid filename")
    return PurePath(cleaned).name


class DocumentService:
    """Business operations over document rows and parent chunks."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Create service bound to an async session factory."""
        self._repo = DocumentRepository(session_factory)

    async def get_document_by_hash(self, file_hash: str) -> Documents | None:
        """Return existing document by file hash if present."""
        return await self._repo.get_document_by_hash(file_hash)

    async def create_doc(
        self,
        filename: str,
        file_hash: str,
        meta: dict | None = None,
        *,
        doc_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Create document with deduplication logic by hash and status."""
        safe_name = _sanitize_filename(filename)
        existing = await self._repo.get_document_by_hash(file_hash)
        if existing is not None:
            if existing.status == DocumentStatus.completed:
                return existing.id
            if existing.status == DocumentStatus.error:
                await self._repo.delete_document(existing.id)
            else:
                return existing.id

        return await self._repo.create_document(safe_name, file_hash, meta, doc_id=doc_id)

    async def add_parent_chunks(self, doc_id: uuid.UUID, parents: list[dict]) -> None:
        """Append parent chunks for a document."""
        if not parents:
            return

        current_max = await self._repo.get_max_chunk_index(doc_id)
        start_index = (current_max + 1) if current_max is not None else 0

        rows = []
        for idx, parent in enumerate(parents):
            rows.append(
                {
                    "id": parent.get("id", uuid.uuid4()),
                    "content": str(parent["text"]),
                    "page_num": str(parent.get("page_num") or ""),
                    "headers": parent.get("headers") or {},
                    "chunk_index": start_index + idx,
                }
            )

        await self._repo.bulk_insert_chunks(doc_id, rows)

    async def set_status(
        self,
        doc_id: uuid.UUID,
        status: DocumentStatus,
        *,
        chunk_count: int | None = None,
    ) -> None:
        """Set document status and optionally update child chunk count."""
        await self._repo.set_status(doc_id, status, chunk_count=chunk_count)

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        """Delete document and all linked chunks by cascade."""
        await self._repo.delete_document(doc_id)


class DocumentQueryService:
    """Read-only queries over document metadata and chunks."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """Create query service bound to an async session factory."""
        self._repo = DocumentRepository(session_factory)

    async def get_document_by_id(self, doc_id: uuid.UUID) -> Documents | None:
        """Return one document by id."""
        return await self._repo.get_document_by_id(doc_id)

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
        """Return documents with filters and pagination."""
        return await self._repo.list_documents(
            limit=limit,
            offset=offset,
            status=status,
            filename=filename,
            created_from=created_from,
            created_to=created_to,
        )

    async def get_parent_chunks(
        self,
        requested_parent_ids: list[uuid.UUID],
        doc_id: uuid.UUID | None = None,
    ) -> list[ParentChunks]:
        """Return parent chunks by ids, optionally scoped to one document."""
        return await self._repo.get_parents_by_ids(requested_parent_ids, doc_id=doc_id)
