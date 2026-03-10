# rag_service/services/ingestion_service.py
from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


from rag_service.core.exceptions import DocumentAlreadyExists
from rag_service.models import DocumentStatus
from rag_service.providers.vector_provider import VectorProvider
from rag_service.rag_core_test.ChinkingEngine import DocumentProcessor
from rag_service.repositories.document_repository import DocumentRepository
from rag_service.services.document_service import DocumentService


@dataclass(frozen=True)
class IngestionResult:
    doc_id: uuid.UUID
    status: DocumentStatus


class IngestionService:
    """
    Тонкая обёртка над ChinkingEngine + DocumentService + VectorProvider.

    Два публичных метода:
        ingest_path(file_path)  ← для Celery (файл уже на диске)
        ingest_bytes(content)   ← для прямой загрузки (пишем tmp и вызываем ingest_path)
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        vector_provider: VectorProvider,
        *,
        vector_timeout_seconds: float = 60.0,
        minio_provider,
    ) -> None:
        self._session_factory = session_factory
        self._vector_provider = vector_provider
        self._vector_timeout_seconds = vector_timeout_seconds
        self._chunker = DocumentProcessor()
        self.minio_provider = minio_provider

    @staticmethod
    def calculate_file_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    # ── public ────────────────────────────────────────────────

    async def ingest_path(
        self,
        file_path: str,
        *,
        doc_id: uuid.UUID | None = None,
        meta: dict | None = None,
    ) -> IngestionResult:
        """Точка входа для Celery — принимает путь к файлу на диске."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            content = f.read()
        if not content:
            raise ValueError("Empty file")

        file_hash = self.calculate_file_hash(content)

        async with self._session_factory() as session:
            return await self._run_pipeline(
                session,
                file_path=file_path,
                filename=filename,
                file_hash=file_hash,
                doc_id=doc_id,
                meta=meta,
            )

    async def ingest_bytes(
        self,
        filename: str,
        content: bytes,
        *,
        doc_id: uuid.UUID | None = None,
        meta: dict | None = None,
    ) -> IngestionResult:
        """Точка входа для прямой загрузки — пишет tmp-файл и вызывает ingest_path."""
        if not content:
            raise ValueError("Empty file")

        suffix = Path(filename).suffix or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            return await self.ingest_path(tmp_path, doc_id=doc_id, meta=meta)
        finally:
            os.unlink(tmp_path)

    # ── private ───────────────────────────────────────────────

    async def _run_pipeline(
        self,
        session: AsyncSession,
        *,
        file_path: str,
        filename: str,
        file_hash: str,
        doc_id: uuid.UUID | None,
        meta: dict | None,
    ) -> IngestionResult:
        """Полный пайплайн внутри одной сессии."""
        service = DocumentService(session)

        # 2. Создаём запись в Postgres (status=processing)
        created_id = await service.create_doc(filename, file_hash, meta, doc_id=doc_id)

        try:
            # 3. ChinkingEngine — весь пайплайн разбивки
            all_data  = self._chunker.process_document(file_path)

            if not all_data:
                raise ValueError("No chunks produced")

            # разделяем parents и children
            parents = [
                {
                    "id": str(uuid.uuid4()),  # ← генерируем полный UUID здесь
                    "text": p["text"],
                    "page_num": p["page_num"],
                    "headers": p["headers"],
                    "_orig_id": p["id"],  # ← сохраняем короткий id для маппинга детей
                }
                for p in all_data
            ]
            id_map = {p["_orig_id"]: p["id"] for p in parents}
            children = [
                {
                    "id": str(uuid.uuid4()),
                    "parent_id": id_map[child["parent_id"]],  # ← маппим на полный UUID
                    "text": child["text"],
                    "page_num": p["page_num"],
                    "headers": p["headers"],
                    "source": p.get("source", ""),
                }
                for p in all_data
                for child in p["children"]
            ]

            if not children:
                raise ValueError("No child chunks produced")

            # 4. Postgres ← родители (контекст для LLM)
            await service.add_parent_chunks(created_id, parents)

            # 5. Qdrant ← дети (для поиска) с богатым payload
            points = [
                {
                    "id":      child["id"],
                    "text":    child["text"],
                    "payload": {
                        "parent_id": child["parent_id"],
                        "page_num":  child["page_num"],
                        "headers":   child["headers"],
                        "source":    child["source"],
                        "doc_id":    str(created_id),
                    },
                }
                for child in children
            ]

            await self._vector_provider.upsert_with_payload(created_id, points)

            # 6. completed
            await service.set_status(created_id, DocumentStatus.completed)
            await session.commit()

            return IngestionResult(created_id, DocumentStatus.completed)

        except Exception:
            await session.rollback()
            await self._mark_error(session, created_id)
            raise

    async def _mark_error(self, session: AsyncSession, doc_id: uuid.UUID) -> None:
        """Отдельная сессия для записи ошибки — основная уже откачена."""
        try:
            async with self._session_factory() as err_session:
                service = DocumentService(err_session)
                await service.set_status(doc_id, DocumentStatus.error)
                await err_session.commit()
        except Exception:
            pass