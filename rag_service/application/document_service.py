"""Service layer for document metadata and parent chunk persistence."""

from __future__ import annotations

import uuid
from pathlib import PurePath
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import IntegrityError

from rag_service.domain.errors.postgres import DocumentAlreadyExists
from rag_service.infrastructures.repositories.document_repository import DocumentRepository
from rag_service.models import DocumentStatus, DocumentListItemDTO, ParentChunks


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

    async def get_document_by_s3key(self, s3key: str) -> DocumentListItemDTO | None:
        """Return one document by storage key.

        Args:
            s3key: Object key stored in `documents.s3key`.

        Returns:
            Matching document row or `None`.
        """
        async with self.session_scope() as (_, repo):
            return await repo.get_document_by_s3key(s3key)

    async def update_document_hash_atomically(self, doc_id: uuid.UUID, file_hash: str, status: str) -> bool:
        """
            Attempts to link a file hash to a document record while ensuring uniqueness.

            The method wraps the repository call in a transaction and catches 
            IntegrityErrors specifically related to the file hash unique constraint.
            This prevents 'race conditions' where two workers might try to process 
            identical files simultaneously.

            Args:
                doc_id: The UUID of the document record created during upload.
                file_hash: Computed SHA-256 hash of the uploaded file.
                status: Transition status to set if unique (e.g., DocumentStatus.EXTRACTING).

            Returns:
                bool: True if the hash was successfully linked (unique file).
                      False if a duplicate hash was detected (file already exists in system).

            Raises:
                IntegrityError: For any database integrity violations other than the hash constraint.
                Exception: For general service or connection failures.
        """
        try:

            async with self.session_scope() as (session, repo):
                await repo.update_document_hash_atomically(
                    doc_id=doc_id,
                    file_hash=file_hash,
                    status=status
                )
                await session.commit()
            return True
        except IntegrityError as e:
            if "uq_documents_file_hash" in str(e.orig):
                return False
            raise e


    async def get_document_by_hash(self, file_hash: str) -> DocumentListItemDTO | None:
        async with self.session_scope() as (_, repo):
            return await repo.get_document_by_hash(file_hash)

    async def get_document_by_id(self, doc_id: uuid.UUID) -> DocumentListItemDTO | None:
        async with self.session_scope() as (_, repo):
            return await repo.get_document_by_id(doc_id)

    async def list_documents(
            self,
            *,
            limit: int,
            offset: int,
            status: str | None = None,
            filename: str | None = None,
    ) -> list[DocumentListItemDTO]:
        async with self.session_scope() as (_, repo):
            return await repo.list_documents(limit=limit, offset=offset, status=status, filename=filename)

    async def create_doc(
            self,
            doc_id: uuid.UUID,
            filename: str,
            metadata: dict[str, Any] | None = None,
            s3key: str | None = None,
            file_size: int | None = None,
    ) -> uuid.UUID:
        safe_name = _sanitize_filename(filename)

        async with self.session_scope() as (session, repo):
            existing_by_name = await repo.get_document_by_id(doc_id)

            if existing_by_name:
                raise DocumentAlreadyExists(f"Document {doc_id} already exists")

            new_id = await repo.create_document(filename=safe_name,
                                                metadata=metadata,
                                                s3key=s3key,
                                                doc_status=DocumentStatus.PENDING,
                                                doc_id=doc_id,
                                                file_size=file_size)
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
            s3key: str | None = None,
            file_hash: str | None = None,
    ) -> None:
        """Update selected document fields and commit transaction."""
        async with self.session_scope() as (session, repo):
            await repo.update_document(
                doc_id,
                status=status,
                metadata=metadata,
                chunk_count=chunk_count,
                s3key=s3key,
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
                "s3key": document.s3key,
                "meta": document.meta or {},
                "created_at": document.created_at,
                # Documents model currently has no updated_at column.
                "updated_at": getattr(document, "updated_at", None),
                "chunk_count": document.chunk_count,
            }

    async def get_document_by_filename(self, filename):
        """Return one document by filename.

            Args:
                filename: filename

            Returns:
                Matching document row or `None`.
            """
        async with self.session_scope() as (_, repo):
            return await repo.get_document_by_filename(filename)


class DocumentQueryService:
    """Read-only queries over document metadata and chunks."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[tuple[AsyncSession, DocumentRepository], None]:
        async with self.session_factory() as session:
            yield session, DocumentRepository(session)

    async def get_document_by_id(self, doc_id: uuid.UUID) -> DocumentListItemDTO | None:
        async with self.session_scope() as (_, repo):
            return await repo.get_document_by_id(doc_id)

    async def list_documents(
        self,
        *,
        limit: int,
        offset: int,
        **filters
    ) -> list[DocumentListItemDTO]:
        async with self.session_scope() as (_, repo):
            return await repo.list_documents(limit=limit, offset=offset, **filters)

    async def get_parent_chunks(
        self,
        requested_parent_ids: list[uuid.UUID],
        doc_id: uuid.UUID | None = None,
    ) -> list[ParentChunks]:
        async with self.session_scope() as (_, repo):
            return await repo.get_parents_by_ids(requested_parent_ids, doc_id=doc_id)
