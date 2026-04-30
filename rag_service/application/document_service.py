"""Service layer for document metadata and parent chunk persistence."""

from __future__ import annotations

import uuid
from pathlib import PurePath
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_service.domain.errors.postgres import DocumentAlreadyExists
from rag_service.infrastructures.repositories.document_repository import DocumentRepository
from rag_service.models import DocumentStatus, Documents, ParentChunks


def _sanitize_filename(filename: str) -> str:
    """Normalize uploaded filename and strip path traversal segments."""
    cleaned = filename.replace("\x00", "").replace("\\", "/")
    cleaned = cleaned.split("/")[-1].strip()
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError("Invalid filename")
    return PurePath(cleaned).name


class DataBaseDocumentService:
    """Business operations over document rows and parent chunks."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[tuple[AsyncSession, DocumentRepository], None]:
        """Управляет жизненным циклом сессии и создает репозиторий."""
        async with self.session_factory() as session:
            try:
                yield session, DocumentRepository(session)
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def get_document_by_hash(self, file_hash: str) -> Documents | None:
        async with self.session_scope() as (_, repo):
            return await repo.get_document_by_hash(file_hash)

    async def get_document_by_id(self, doc_id: uuid.UUID) -> Documents | None:
        async with self.session_scope() as (_, repo):
            return await repo.get_document_by_id(doc_id)

    async def list_documents(
            self,
            *,
            limit: int,
            offset: int,
            status: str | None = None,
            filename: str | None = None,
    ) -> list[Documents]:
        async with self.session_scope() as (_, repo):
            return await repo.list_documents(
                limit=limit,
                offset=offset,
                status=status,
                filename=filename,
            )

    async def create_doc(
            self,
            doc_id: uuid.UUID,
            filename: str,
            metadata: dict[str, Any],
            minio_key: str | None = None,

    ) -> uuid.UUID:
        safe_name = _sanitize_filename(filename)

        async with self.session_scope() as (session, repo):
            existing_by_name = await repo.get_document_by_id(doc_id)

            if existing_by_name:
                raise DocumentAlreadyExists(f"Document {doc_id} already exists")

            new_id = await repo.create_document(filename=safe_name,
                                                metadata=metadata,
                                                minio_key=minio_key,
                                                doc_status=DocumentStatus.PENDING,
                                                doc_id=doc_id)
            await session.commit()
            return new_id

    async def add_parent_chunks(self, doc_id: uuid.UUID, parents: list[dict]) -> None:
        if not parents:
            return

        async with self.session_scope() as (session, repo):
            current_max = await repo.get_max_chunk_index(doc_id)
            start_index = (current_max + 1) if current_max is not None else 0

            rows = []
            for idx, parent in enumerate(parents):
                rows.append({
                    "id": parent.get("id", uuid.uuid4()), # Вернул генерацию ID из оригинала
                    "content": str(parent["text"]),
                    "page_num": str(parent.get("page_num") or ""),
                    "headers": parent.get("headers") or {},
                    "chunk_index": start_index + idx,
                })

            await repo.bulk_insert_chunks(doc_id, rows)
            await session.commit()

    async def set_status(
            self,
            doc_id: uuid.UUID,
            status: DocumentStatus,
            *,
            chunk_count: int | None = None,
    ) -> None:
        async with self.session_scope() as (session, repo):
            await repo.set_status(doc_id, status, chunk_count=chunk_count)
            await session.commit()

    async def update_document(
            self,
            doc_id: uuid.UUID,
            *,
            status: str | DocumentStatus | None = None,
            metadata: dict[str, Any] | None = None,
            chunk_count: int | None = None,
            minio_key: str | None = None,
            file_hash: str | None = None,
    ) -> None:
        """Update selected document fields and commit transaction."""
        async with self.session_scope() as (session, repo):
            await repo.update_document(
                doc_id,
                status=status,
                metadata=metadata,
                chunk_count=chunk_count,
                minio_key=minio_key,
                file_hash=file_hash,
            )
            await session.commit()

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        async with self.session_scope() as (session, repo):
            await repo.delete_document(doc_id)
            await session.commit()

    async def update_metadata_document(self, doc_id: uuid.UUID, metadata: dict[str, Any]) -> None:
        pass

    async def get_document_full_info(self, doc_id: uuid.UUID) -> dict[str, Any] | None:
        """Return full document info from Postgres with chunk counters only."""
        async with self.session_scope() as (_, repo):
            document = await repo.get_document_by_id(doc_id)
            if document is None:
                return None

            return {
                "doc_id": str(document.id),
                "filename": document.filename,
                "status": getattr(document.status, "value", str(document.status)),
                "minio_key": document.minio_key,
                "meta": document.meta or {},
                "created_at": document.created_at,
                # Documents model currently has no updated_at column.
                "updated_at": getattr(document, "updated_at", None),
                "chunk_count": document.chunk_count,
            }

class DocumentQueryService:
    """Read-only queries over document metadata and chunks."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[tuple[AsyncSession, DocumentRepository], None]:
        async with self.session_factory() as session:
            yield session, DocumentRepository(session)

    async def get_document_by_id(self, doc_id: uuid.UUID) -> Documents | None:
        async with self.session_scope() as (_, repo):
            return await repo.get_document_by_id(doc_id)

    async def list_documents(
        self,
        *,
        limit: int,
        offset: int,
        **filters
    ) -> list[Documents]:
        async with self.session_scope() as (_, repo):
            return await repo.list_documents(limit=limit, offset=offset, **filters)

    async def get_parent_chunks(
        self,
        requested_parent_ids: list[uuid.UUID],
        doc_id: uuid.UUID | None = None,
    ) -> list[ParentChunks]:
        async with self.session_scope() as (_, repo):
            return await repo.get_parents_by_ids(requested_parent_ids, doc_id=doc_id)
