"""Repository layer for rag document and parent chunk models."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Iterable, Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from rag_service.models import DocumentStatus, DocumentListItemDTO, ParentChunks, DocumentChapters, DocumentTables, DocumentMetaSections


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

    async def get_document_by_filename(self,filename:str)-> DocumentListItemDTO | None:
        return await self._get_one(DocumentListItemDTO.filename == filename)


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
            doc_id: Optional explicit UUID. If omitted, models default is used.

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
            update_data: dict[str, Any | None]
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

        field_mapping = {
            "metadata": "meta",
        }

        for key, value in update_data.items():
            if value is None:
                continue

            # Определяем целевое имя колонки в базе данных
            db_key = field_mapping.get(key, key)

            # Обрабатываем специфичные типы, например Enum статуса
            if db_key == "status":
                values["status"] = getattr(value, "value", value)
            else:
                values[db_key] = value


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

    async def get_chapters_by_doc_id(self, doc_id: uuid.UUID) -> list[DocumentChapters]:
        """Return document chapters in original document order (uuid7 ids sort chronologically).

        Args:
            doc_id: Target document UUID.
        """
        result = await self._session.execute(
            select(DocumentChapters).where(DocumentChapters.doc_id == doc_id).order_by(DocumentChapters.id.asc())
        )
        return list(result.scalars().all())

    async def get_tables_by_doc_id(self, doc_id: uuid.UUID) -> list[DocumentTables]:
        """Return document tables ordered by their position in the document.

        Args:
            doc_id: Target document UUID.
        """
        result = await self._session.execute(
            select(DocumentTables).where(DocumentTables.doc_id == doc_id).order_by(DocumentTables.table_index.asc())
        )
        return list(result.scalars().all())

    async def get_meta_sections_by_doc_id(self, doc_id: uuid.UUID) -> list[DocumentMetaSections]:
        """Return document meta sections (TOC/abbreviations/appendices).

        Args:
            doc_id: Target document UUID.
        """
        result = await self._session.execute(
            select(DocumentMetaSections).where(DocumentMetaSections.doc_id == doc_id)
        )
        return list(result.scalars().all())

    async def update_chapter_summary(self, chapter_id: uuid.UUID, summary: str) -> None:
        """Set the LLM-generated summary for one already-inserted chapter row.

        Args:
            chapter_id: `document_chapters.id` of the target chapter.
            summary: Generated summary text.
        """
        await self._session.execute(
            update(DocumentChapters).where(DocumentChapters.id == chapter_id).values(summary=summary)
        )

    async def update_table_summary(self, table_id: uuid.UUID, summary: str) -> None:
        """Set the LLM-generated summary for one already-inserted table row.

        Args:
            table_id: `document_tables.id` of the target table.
            summary: Generated summary text.
        """
        await self._session.execute(
            update(DocumentTables).where(DocumentTables.id == table_id).values(summary=summary)
        )

    async def update_table_parent_chunk_id(self, table_id: uuid.UUID, parent_chunk_id: uuid.UUID) -> None:
        """Link a table row to the parent_chunks row created for its Qdrant summary point.

        Lets callers check `parent_chunk_id IS NOT NULL` to know a table is already
        vectorized (idempotency for manual re-runs of summarize_document_chapters_task —
        see rag_service/workers/task.py) and JOIN document_tables/parent_chunks directly
        instead of matching on the `[→ Таблица N]` marker text.

        Args:
            table_id: `document_tables.id` of the target table.
            parent_chunk_id: `parent_chunks.id` created for this table's summary point.
        """
        await self._session.execute(
            update(DocumentTables).where(DocumentTables.id == table_id).values(parent_chunk_id=parent_chunk_id)
        )

    async def update_document_summary(self, doc_id: uuid.UUID, summary: str) -> None:
        """Set the LLM-synthesized summary for the whole document.

        Args:
            doc_id: Target document UUID.
            summary: Generated summary text (synthesized from chapter summaries).
        """
        await self._session.execute(
            update(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id).values(summary=summary)
        )

    async def delete_structural_data(self, doc_id: uuid.UUID) -> None:
        """Delete parent chunks, chapters, and tables for a document.

        Used to reset a document's structural data before re-running ingestion
        (e.g. on a Celery retry), so re-insertion doesn't hit unique constraints
        on rows already committed by a previous attempt.

        Args:
            doc_id: Target document UUID.
        """
        await self._session.execute(delete(ParentChunks).where(ParentChunks.doc_id == doc_id))
        await self._session.execute(delete(DocumentChapters).where(DocumentChapters.doc_id == doc_id))
        await self._session.execute(delete(DocumentTables).where(DocumentTables.doc_id == doc_id))
        await self._session.execute(delete(DocumentMetaSections).where(DocumentMetaSections.doc_id == doc_id))

    async def bulk_insert_chapters(self, doc_id: uuid.UUID, chapters: Iterable[dict]) -> None:
        """Bulk insert document chapters (one document has tens of chapters, no batching needed).

        Args:
            doc_id: Target document UUID used for all inserted rows.
            chapters: Iterable of dicts with `chapter_number`, `title`, `s3_md_path`.
        """
        rows = [
            {
                "doc_id": doc_id,
                "chapter_number": chapter["chapter_number"],
                "title": chapter["title"],
                "s3_md_path": chapter["s3_md_path"],
            }
            for chapter in chapters
        ]
        if not rows:
            return

        await self._session.execute(insert(DocumentChapters), rows)

    async def bulk_insert_tables(self, doc_id: uuid.UUID, tables: Iterable[dict]) -> None:
        """Bulk insert document tables (one document has tens of tables, no batching needed).

        Args:
            doc_id: Target document UUID used for all inserted rows.
            tables: Iterable of dicts with `table_index`, `s3_csv_path`, `s3_html_path`.
        """
        rows = [
            {
                "doc_id": doc_id,
                "table_index": table["table_index"],
                "s3_csv_path": table["s3_csv_path"],
                "s3_html_path": table["s3_html_path"],
            }
            for table in tables
        ]
        if not rows:
            return

        await self._session.execute(insert(DocumentTables), rows)

    async def bulk_insert_meta_sections(self, doc_id: uuid.UUID, sections: Iterable[dict]) -> None:
        """Bulk insert document meta sections (TOC/abbreviations/appendices - at most a few per document).

        Args:
            doc_id: Target document UUID used for all inserted rows.
            sections: Iterable of dicts with `section_type`, `s3_md_path`.
        """
        rows = [
            {
                "doc_id": doc_id,
                "section_type": section["section_type"],
                "s3_md_path": section["s3_md_path"],
            }
            for section in sections
        ]
        if not rows:
            return

        await self._session.execute(insert(DocumentMetaSections), rows)
