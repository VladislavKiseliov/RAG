"""Service layer for document metadata and parent chunk models."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import IntegrityError

from rag_service.domain.chunking.chunk_builder import ParentChunk
from rag_service.domain.document import _sanitize_filename
from rag_service.domain.errors.postgres import DocumentAlreadyExists
from rag_service.infrastructures.repositories.document_repository import DocumentRepository
from rag_service.models import DocumentStatus, DocumentListItemDTO, ParentChunks


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

    async def update_document_hash_atomically(self, doc_id: uuid.UUID, file_hash: str, status: DocumentStatus) -> bool:
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
                    status=status.value
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
            existing_by_id = await repo.get_document_by_id(doc_id)

            if existing_by_id:
                raise DocumentAlreadyExists(f"Document {doc_id} already exists")

            new_id = await repo.create_document(filename=safe_name,
                                                metadata=metadata,
                                                s3key=s3key,
                                                doc_status=DocumentStatus.PENDING,
                                                doc_id=doc_id,
                                                file_size=file_size)
            await session.commit()
            return new_id

    async def add_parent_chunks(self, doc_id: uuid.UUID, parents: list[ParentChunk]) -> None:
        if not parents:
            return

        async with self.session_scope() as (session, repo):
            current_max = await repo.get_max_chunk_index(doc_id)
            start_index = (current_max + 1) if current_max is not None else 0

            rows = []
            for idx, parent in enumerate(parents):
                rows.append({
                    "id": parent.id,
                    "content": parent.text,
                    "page_num": "",
                    "headers": parent.headers,
                    "chunk_index": start_index + idx,
                })

            await repo.bulk_insert_chunks(doc_id, rows)
            await session.commit()

    async def reset_structural_data(self, doc_id: uuid.UUID) -> None:
        """Delete parent chunks, chapters, and tables for a document (retry reset)."""
        async with self.session_scope() as (session, repo):
            await repo.delete_structural_data(doc_id)
            await session.commit()

    async def add_document_chapters(self, doc_id: uuid.UUID, chapters: list[dict]) -> None:
        if not chapters:
            return

        async with self.session_scope() as (session, repo):
            await repo.bulk_insert_chapters(doc_id, chapters)
            await session.commit()

    async def get_chapters_by_doc_id(self, doc_id: uuid.UUID) -> list:
        async with self.session_scope() as (_, repo):
            return await repo.get_chapters_by_doc_id(doc_id)

    async def update_chapter_summary(self, chapter_id: uuid.UUID, summary: str) -> None:
        async with self.session_scope() as (session, repo):
            await repo.update_chapter_summary(chapter_id, summary)
            await session.commit()

    async def update_document_summary(self, doc_id: uuid.UUID, summary: str) -> None:
        async with self.session_scope() as (session, repo):
            await repo.update_document_summary(doc_id, summary)
            await session.commit()

    async def update_table_summary(self, table_id: uuid.UUID, summary: str) -> None:
        async with self.session_scope() as (session, repo):
            await repo.update_table_summary(table_id, summary)
            await session.commit()

    async def update_table_parent_chunk_id(self, table_id: uuid.UUID, parent_chunk_id: uuid.UUID) -> None:
        async with self.session_scope() as (session, repo):
            await repo.update_table_parent_chunk_id(table_id, parent_chunk_id)
            await session.commit()

    async def add_document_tables(self, doc_id: uuid.UUID, tables: list[dict]) -> None:
        if not tables:
            return

        async with self.session_scope() as (session, repo):
            await repo.bulk_insert_tables(doc_id, tables)
            await session.commit()

    async def get_tables_by_doc_id(self, doc_id: uuid.UUID) -> list:
        async with self.session_scope() as (_, repo):
            return await repo.get_tables_by_doc_id(doc_id)

    async def add_document_meta_sections(self, doc_id: uuid.UUID, sections: list[dict]) -> None:
        if not sections:
            return

        async with self.session_scope() as (session, repo):
            await repo.bulk_insert_meta_sections(doc_id, sections)
            await session.commit()

    async def get_meta_sections_by_doc_id(self, doc_id: uuid.UUID) -> list:
        async with self.session_scope() as (_, repo):
            return await repo.get_meta_sections_by_doc_id(doc_id)

    async def add_abbreviations(self, doc_id: uuid.UUID, pairs: list[dict]) -> None:
        if not pairs:
            return

        async with self.session_scope() as (session, repo):
            await repo.bulk_insert_abbreviations(doc_id, pairs)
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
            update_data: dict[str, Any | None]
    ) -> None:
        """Update selected document fields and commit transaction."""
        async with self.session_scope() as (session, repo):
            await repo.update_document(
                doc_id,
                update_data=update_data
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
                # Documents models currently has no updated_at column.
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

    async def get_chapters_by_doc_id(self, doc_id: uuid.UUID) -> list:
        async with self.session_scope() as (_, repo):
            return await repo.get_chapters_by_doc_id(doc_id)

    async def get_tables_by_doc_id(self, doc_id: uuid.UUID) -> list:
        async with self.session_scope() as (_, repo):
            return await repo.get_tables_by_doc_id(doc_id)

    async def get_meta_sections_by_doc_id(self, doc_id: uuid.UUID) -> list:
        async with self.session_scope() as (_, repo):
            return await repo.get_meta_sections_by_doc_id(doc_id)

    async def get_all_abbreviations(self) -> list:
        async with self.session_scope() as (_, repo):
            return await repo.get_all_abbreviations()
