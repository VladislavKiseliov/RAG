"""Ingestion pipeline: validation, dedup, parent/child chunking, DB write, Qdrant upsert."""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_service.core.exceptions import DocumentAlreadyExists
from rag_service.models import DocumentStatus
from rag_service.providers.vector_provider import VectorProvider
from rag_service.rag_core_test.ChinkingEngine import DocumentProcessor
from rag_service.repositories.document_repository import DocumentRepository
from rag_service.services.document_service import DocumentService


@dataclass(frozen=True)
class IngestionResult:
    """Result DTO for ingestion operations."""

    doc_id: uuid.UUID
    status: DocumentStatus



class IngestionService:
    """Orchestrates document ingestion into Postgres and Qdrant."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        vector_provider: VectorProvider,
        *,
        vector_timeout_seconds: float = 60.0,
        child_chunk_size: int = 400,
        child_chunk_overlap: int = 40,
    ) -> None:
        """Initialize service with DB session factory and vector backend."""
        self._session_factory = session_factory
        self._vector_provider = vector_provider
        self._vector_timeout_seconds = vector_timeout_seconds
        self._chunk_engine = DocumentProcessor()

    @staticmethod
    def calculate_file_hash(content: bytes) -> str:
        """Return SHA-256 hash used for deduplication."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _extract_text_from_txt(content: bytes) -> str:
        """Decode TXT content as UTF-8 with ignore-errors strategy."""
        return content.decode("utf-8", errors="ignore")

    @staticmethod
    def _extract_pages_from_pdf(content: bytes) -> list[dict]:
        """Extract PDF text page-by-page using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required to extract PDF text") from exc

        pages: list[dict] = []
        with fitz.open(stream=content, filetype="pdf") as doc:
            for idx, page in enumerate(doc, start=1):
                pages.append({"page_num": str(idx), "text": page.get_text()})
        return pages

    @staticmethod
    def _extract_text_from_docx(content: bytes) -> str:
        """Extract text from DOCX by concatenating paragraph text."""
        try:
            import docx  # python-docx
        except ImportError as exc:
            raise RuntimeError("python-docx is required to extract DOCX text") from exc

        document = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in document.paragraphs)

    @staticmethod
    def _infer_content_type(filename: str) -> str | None:
        """Infer MIME type from file extension."""
        name = filename.lower()
        if name.endswith(".pdf"):
            return "application/pdf"
        if name.endswith(".docx"):
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if name.endswith(".txt"):
            return "text/plain"
        return None

    def extract_pages(self, content: bytes, *, filename: str, content_type: str | None) -> list[dict]:
        """Extract document into normalized pages with `page_num` and `text`."""
        if not content:
            raise ValueError("Empty file")

        effective_type = content_type or self._infer_content_type(filename)
        name_lower = filename.lower()

        if effective_type == "application/pdf" or name_lower.endswith(".pdf"):
            return self._extract_pages_from_pdf(content)

        if effective_type == "text/plain" or name_lower.endswith(".txt"):
            return [{"page_num": "1", "text": self._extract_text_from_txt(content)}]

        if (
            effective_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or name_lower.endswith(".docx")
        ):
            text = self._extract_text_from_docx(content)
            return [{"page_num": "1", "text": text}]

        raise ValueError("Unsupported file type")

    async def ingest_path(
        self,
        file_path: str,
        *,
        content_type: str | None = None,
        meta: dict | None = None,
        doc_id: uuid.UUID | None = None,
    ) -> IngestionResult:
        """Ingest document from filesystem path."""
        if not os.path.exists(file_path):
            raise ValueError("File path does not exist")
        if not os.path.isfile(file_path):
            raise ValueError("Path is not a file")

        filename = os.path.basename(file_path)
        content = open(file_path, "rb").read()
        if not content:
            raise ValueError("Empty file")

        inferred = content_type or self._infer_content_type(filename)
        if inferred is None:
            raise ValueError("Unsupported file type")

        return await self.ingest_bytes(
            filename=filename,
            content=content,
            content_type=inferred,
            meta=meta,
            doc_id=doc_id,
        )

    async def ingest_bytes(
        self,
        filename: str,
        content: bytes,
        *,
        content_type: str | None = None,
        meta: dict | None = None,
        doc_id: uuid.UUID | None = None,
    ) -> IngestionResult:
        """Ingest in-memory bytes using an internally created DB session."""
        async with self._session_factory() as session:
            return await self.ingest_with_session(
                session,
                filename=filename,
                content=content,
                content_type=content_type,
                meta=meta,
                doc_id=doc_id,
            )

    async def ingest_with_session(
        self,
        session: AsyncSession,
        *,
        filename: str,
        content: bytes,
        content_type: str | None,
        meta: dict | None,
        doc_id: uuid.UUID | None,
    ) -> IngestionResult:
        """Run full ingestion pipeline inside provided DB session."""
        file_hash = self.calculate_file_hash(content)
        repo = DocumentRepository(session)
        service = DocumentService(session)

        existing = await repo.get_document_by_hash(file_hash)
        if existing is not None:
            if existing.status == DocumentStatus.completed:
                return IngestionResult(existing.id, DocumentStatus.completed)
            if existing.status == DocumentStatus.processing:
                return IngestionResult(existing.id, DocumentStatus.processing)

        pages = self.extract_pages(content, filename=filename, content_type=content_type)
        parents, children = self._chunk_engine.process_document(pages=pages, source=filename)

        if not parents:
            raise ValueError("No parent chunks produced")
        if not children:
            raise ValueError("No child chunks produced")

        tx = await session.begin()
        try:
            if existing is not None and existing.status == DocumentStatus.error:
                await repo.delete_document(existing.id)
                await session.flush()

            created_id = await service.create_doc(filename, file_hash, meta, doc_id=doc_id)
            await service.add_parent_chunks(created_id, parents)

            points: list[dict] = []
            for idx, child in enumerate(children):
                payload = dict(child.get("payload") or {})
                payload["doc_id"] = str(created_id)
                points.append(
                    {
                        "id": child.get("id") or f"{created_id}:{idx}",
                        "text": child["text"],
                        "payload": payload,
                    }
                )

            await asyncio.wait_for(
                self._vector_provider.upsert_with_payload(created_id, points),
                timeout=self._vector_timeout_seconds,
            )

            await service.set_status(created_id, DocumentStatus.completed, chunk_count=len(points))
            await session.commit()
            return IngestionResult(created_id, DocumentStatus.completed)
        except DocumentAlreadyExists:
            await session.rollback()
            existing = await repo.get_document_by_hash(file_hash)
            if existing is not None:
                return IngestionResult(existing.id, existing.status)
            raise
        except Exception:
            await session.rollback()
            raise
        finally:
            if tx.is_active:
                await tx.rollback()
