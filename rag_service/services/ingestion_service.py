from __future__ import annotations

import asyncio
import hashlib
import io
import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_service.core.exceptions import DocumentAlreadyExists
from rag_service.models import DocumentStatus
from rag_service.repositories.document_repository import DocumentRepository
from rag_service.services.document_service import DocumentService
from rag_service.providers.vector_provider import VectorProvider


@dataclass(frozen=True)
class IngestionResult:
    doc_id: uuid.UUID
    status: DocumentStatus


class IngestionService:
    """Оркестратор загрузки документов в RAG.

    Пайплайн:
    - вычисление хэша
    - извлечение и препроцессинг текста
    - чанкирование
    - запись в Postgres (processing)
    - запись в векторное хранилище
    - перевод в completed и commit
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        vector_provider: VectorProvider,
        *,
        chunk_size: int = 900,
        overlap_ratio: float = 0.1,
        vector_timeout_seconds: float = 60.0,
    ) -> None:
        self._session_factory = session_factory
        self._vector_provider = vector_provider
        self._chunk_size = chunk_size
        self._overlap_ratio = overlap_ratio
        self._vector_timeout_seconds = vector_timeout_seconds

    @staticmethod
    def calculate_file_hash(content: bytes) -> str:
        """SHA-256 для дедупликации документов."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _preprocess_text(text: str) -> str:
        """Простейшая очистка: нормализация пробелов и удаление управляющих символов."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _extract_text_from_txt(content: bytes) -> str:
        return content.decode("utf-8", errors="ignore")

    @staticmethod
    def _extract_text_from_pdf(content: bytes) -> str:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise RuntimeError("PyMuPDF is required to extract PDF text") from exc

        with fitz.open(stream=content, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)

    @staticmethod
    def _extract_text_from_docx(content: bytes) -> str:
        try:
            import docx  # python-docx
        except ImportError as exc:
            raise RuntimeError("python-docx is required to extract DOCX text") from exc

        document = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in document.paragraphs)

    def extract_text(self, content: bytes, *, filename: str, content_type: str | None) -> str:
        """Извлекает текст из PDF/TXT/DOCX по MIME или расширению."""
        name_lower = filename.lower()
        if content_type == "application/pdf" or name_lower.endswith(".pdf"):
            return self._extract_text_from_pdf(content)
        if content_type == "text/plain" or name_lower.endswith(".txt"):
            return self._extract_text_from_txt(content)
        if (
            content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or name_lower.endswith(".docx")
        ):
            return self._extract_text_from_docx(content)
        raise ValueError("Unsupported file type")

    def split_into_chunks(self, text: str) -> list[str]:
        """Разбивает текст на чанки по словам, имитируя токены."""
        if not text:
            return []
        words = text.split()
        if not words:
            return []

        chunk_size = max(1, self._chunk_size)
        overlap = max(0, int(chunk_size * self._overlap_ratio))
        step = max(1, chunk_size - overlap)

        chunks: list[str] = []
        for start in range(0, len(words), step):
            chunk_words = words[start : start + chunk_size]
            if not chunk_words:
                continue
            chunks.append(" ".join(chunk_words))
        return chunks

    async def ingest_bytes(
        self,
        filename: str,
        content: bytes,
        *,
        content_type: str | None = None,
        meta: dict | None = None,
        doc_id: uuid.UUID | None = None,
    ) -> IngestionResult:
        """Полный пайплайн с открытием своей AsyncSession."""
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
        """Полный пайплайн в рамках предоставленной сессии.

        Коммит выполняется только после успешной записи в векторное хранилище.
        """
        file_hash = self.calculate_file_hash(content)
        repo = DocumentRepository(session)
        service = DocumentService(session)

        text = self._preprocess_text(self.extract_text(content, filename=filename, content_type=content_type))
        if not text:
            raise ValueError("Extracted text is empty")

        chunks = self.split_into_chunks(text)
        if not chunks:
            raise ValueError("Chunking produced no chunks")

        existing = await repo.get_document_by_hash(file_hash)
        if existing is not None:
            if existing.status == DocumentStatus.completed:
                return IngestionResult(existing.id, DocumentStatus.completed)
            if existing.status == DocumentStatus.processing:
                return IngestionResult(existing.id, DocumentStatus.processing)

        tx = await session.begin()
        try:
            if existing is not None and existing.status == DocumentStatus.error:
                await repo.delete_document(existing.id)
                await session.flush()

            created_id = await service.create_doc(filename, file_hash, meta, doc_id=doc_id)
            await service.add_chunks(created_id, chunks)

            await asyncio.wait_for(
                self._vector_provider.upsert(created_id, chunks, meta),
                timeout=self._vector_timeout_seconds,
            )

            await service.set_status(created_id, DocumentStatus.completed)
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
