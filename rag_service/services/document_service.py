"""Service layer for document metadata and parent chunk persistence."""

from __future__ import annotations

import uuid
from pathlib import PurePath

from sqlalchemy.ext.asyncio import AsyncSession

from rag_service.models import DocumentStatus
from rag_service.repositories.document_repository import DocumentRepository


def _sanitize_filename(filename: str) -> str:
    """Normalize uploaded filename and strip path traversal segments."""
    cleaned = filename.replace("\x00", "").replace("\\", "/")
    cleaned = cleaned.split("/")[-1].strip()
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("Invalid filename")
    return PurePath(cleaned).name


class DocumentService:
    """Business operations over document rows and parent chunks."""

    def __init__(self, session: AsyncSession) -> None:
        """Create service bound to an existing session."""
        self._session = session
        self._repo = DocumentRepository(session)

    async def get_document_by_hash(self, file_hash: str):
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
                await self._session.flush()
            else:
                return existing.id

        return await self._repo.create_doc(safe_name, file_hash, meta, doc_id=doc_id)

    async def add_parent_chunks(self, doc_id: uuid.UUID, parents: list[dict]) -> None:
        """Persist parent chunks for a document with auto-incremented chunk_index."""
        if not parents:
            return

        current_max = await self._repo.get_max_chunk_index(doc_id)
        start_index = (current_max + 1) if current_max is not None else 0

        rows = []
        for idx, parent in enumerate(parents):
            rows.append(
                {
                    "parent_id": str(parent["parent_id"]),
                    "text": str(parent["text"]),
                    "page_num": str(parent.get("page_num") or ""),
                    "headers": parent.get("headers") or {},
                    "chunk_index": start_index + idx,
                }
            )

        await self._repo.bulk_insert_chunks(doc_id, rows)

    async def set_status(self, doc_id: uuid.UUID, status: DocumentStatus, *, chunk_count: int | None = None) -> None:
        """Set document status and optionally update child chunk count."""
        await self._repo.set_status(doc_id, status, chunk_count=chunk_count)

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        """Delete document and all linked chunks by cascade."""
        await self._repo.delete_document(doc_id)

    async def get_full_text(self, doc_id: uuid.UUID) -> str:
        """Return full document text reconstructed from parent chunks."""
        return await self._repo.get_full_text(doc_id)
