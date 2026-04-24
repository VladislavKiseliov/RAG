from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from dataclasses import dataclass

from rag_service.application.chunking_pipeline import DocumentChunkingPipeline
from rag_service.application.document_service import DocumentService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.infrastructures.providers.s3_storage_provider import S3StorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider
from rag_service.models import DocumentStatus


@dataclass(frozen=True)
class IngestionResult:
    doc_id: uuid.UUID
    status: DocumentStatus


class IngestionService:
    """Orchestrates document ingestion and child chunk upload into vector DB."""

    def __init__(
        self,
        document_service: DocumentService,
        vector_storage: VectorStorageProvider,
        vector_indexing_service: VectorIndexingService,
        *,
        vector_timeout_seconds: float = 60.0,
        s3_storage: S3StorageProvider,
    ) -> None:
        self._document_service = document_service
        self.vector_storage = vector_storage
        self._vector_indexing_service = vector_indexing_service
        self._vector_timeout_seconds = vector_timeout_seconds
        self._chunker = DocumentChunkingPipeline()
        self.s3_storage = s3_storage

    async def _register_document(self, file_bytes: bytes, doc_id: uuid.UUID, meta: dict | None = None) -> str:
        """
        1. Считает хеш.
        2. Проверяет дубликаты.
        3. Создает запись в БД со статусом 'processing'.
        """
        file_hash = await self._compute_hash(file_bytes)

        # Проверка на дубликат
        existing = await self._document_service.get_by_hash(file_hash)
        if existing:
            # Можно либо выкинуть ошибку, либо вернуть спец. статус
            raise ValueError(f"Document with hash {file_hash} already exists")

        await self._document_service.create_doc(
            doc_id=doc_id,
            filename=os.path.basename(file_path),
            file_hash=file_hash,
            meta=meta,
            status=DocumentStatus.processing
        )
        return file_hash

    async def extract_and_store_chunks(self, doc_id: uuid.UUID, file_path: str):
        """
        1. Парсит файл через Pipeline.
        2. Сохраняет родительские чанки в Postgres.
        """
        # Твой тяжелый Pipeline
        parents, children = self._chunker.process(file_path)

        if not parents:
            raise ValueError("No content extracted from document")

        # Сохраняем структуру в SQL (текст + метаданные)
        await self._document_service.add_parent_chunks(doc_id, parents)

        # Возвращаем детей, чтобы передать их на векторизацию
        return children

    async def index_vectors(self, doc_id: uuid.UUID, children: list):
        """
        1. Превращает детей в точки (points).
        2. Пушит в Qdrant.
        3. Ставит финальный статус 'completed'.
        """
        points = [
            {
                "id": child.get("id") or str(uuid.uuid4()),
                "text": child["text"],
                "payload": {
                    "parent_id": child["parent_id"],
                    "headers": child.get("headers") or {},
                    "source": child.get("source", ""),
                    "doc_id": str(doc_id),
                },
            }
            for child in children
        ]

        await self._vector_indexing_service.upsert_points(points)

        await self._document_service.set_status(
            doc_id,
            DocumentStatus.completed,
            chunk_count=len(points)
        )
    @staticmethod
    def _compute_hash(file_bytes: bytes) -> str:
        """Вычисляет SHA-256 хеш из байтов файла."""
        return hashlib.sha256(file_bytes).hexdigest()

    async def _calculate_hash_async(self, file_path: str) -> str:
        def _sync_hash():
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest()

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_hash)

    async def process_document(self,doc_id: uuid.UUID, minio_key: str):
        try:
            file_bytes = await self.s3_storage.get_file(minio_key)

            file_hash = self._register_document(file_bytes=file_bytes, doc_id=doc_id, meta=None)




        except:








