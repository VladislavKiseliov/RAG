from __future__ import annotations

import asyncio
import hashlib
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional

from rag_service.application.chunking_pipeline import DocumentChunkingPipeline
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.infrastructures.providers.s3_storage_provider import S3StorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider
from rag_service.models import DocumentStatus, DocumentListItemDTO


@dataclass(frozen=True)
class IngestionResult:
    """Result of the document ingestion process."""
    doc_id: uuid.UUID
    status: DocumentStatus


class IngestionService:
    """
    Orchestrates the document ingestion and indexing pipeline.

    This service coordinates interactions between S3 storage, relational database (SQL),
    document parsing pipelines, and the vector database (Qdrant).

    Responsibilities:
        - Manage document lifecycle states (processing, indexing, completed, error).
        - Coordinate file downloading, hashing, and parsing.
        - Orchestrate batch vectorization and storage.
    """

    def __init__(
            self,
            document_service: DataBaseDocumentService,
            vector_storage: VectorStorageProvider,
            vector_indexing_service: VectorIndexingService,
            s3_storage: S3StorageProvider,
            vector_timeout_seconds: float = 60.0,
    ) -> None:
        """
        Initializes the IngestionService with required providers.

        Args:
            document_service: Service for SQL database operations.
            vector_storage: Provider for vector database operations.
            vector_indexing_service: Service for generating text embeddings.
            s3_storage: Provider for file storage (S3/Minio).
            vector_timeout_seconds: Timeout for vectorization operations.
        """
        self._document_service = document_service
        self.vector_storage = vector_storage
        self.vector_indexing_service = vector_indexing_service
        self.s3_storage = s3_storage
        self._vector_timeout_seconds = vector_timeout_seconds
        self._chunker = DocumentChunkingPipeline()

    async def process_document(self, doc_id: uuid.UUID, s3key: str) -> IngestionResult:
        """
        Executes the full ingestion pipeline for a single document.

        Pipeline stages:
            1. Download file from S3.
            2. Register document in SQL (hash check & duplicate prevention).
            3. Extract chunks using the parsing pipeline.
            4. Generate embeddings for extracted chunks.
            5. Store vectors and metadata in the vector database.
            6. Finalize document status.

        Args:
            doc_id: Unique identifier for the document.
            s3key: The key (path) of the file in the S3 bucket.

        Returns:
            IngestionResult: The final state and ID of the processed document.

        Raises:
            Exception: If any stage fails, updates document status to 'error' and re-raises.
        """
        path_obj = Path(s3key)
        file_name = path_obj.name

        try:
            # 1. Скачивание (S3 -> Memory)
            # Мы сначала качаем файл, чтобы вычислить его хеш
            file_bytes = await self.s3_storage.get_file(s3key)
            file_hash = self._compute_hash(file_bytes)

            # 2. АТОМАРНАЯ ПРОВЕРКА И ОБНОВЛЕНИЕ
            success = await self._document_service.update_document_hash_atomically(
                doc_id=doc_id,
                file_hash=file_hash,
                status=DocumentStatus.EXTRACTING
            )

            if not success:
                print(12234)
                # Логика для дубликата:
                # Ставим статус DUPLICATE и удаляем временный файл из S3 (экономя место)
                await self._document_service.delete_document(doc_id=doc_id)
                await self.s3_storage.delete_file(s3key)

                return IngestionResult(doc_id=doc_id, status=DocumentStatus.DUPLICATE)

            # 3. ЕСЛИ НЕ ДУБЛИКАТ — ПРОДОЛЖАЕМ
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir) / file_name

                # Сохраняем байты во временный файл для парсинга
                with open(tmp_path, "wb") as f:
                    f.write(file_bytes)

                # 4. Извлечение текста и сохранение чанков в SQL
                children = await self.extract_and_store_chunks(doc_id, str(tmp_path))

                # 5. Обновляем статус: Переходим к векторизации
                await self._document_service.update_document(
                    doc_id,
                    status=DocumentStatus.INDEXING,
                )

                # 6. Генерация эмбеддингов
                vectors = await self.index_vectors(children)

                # 7. Сохранение в векторную БД (Qdrant)
                await self.vector_storage.upsert_vectors(doc_id, children, vectors)

                # 8. Финализация: Успех
                await self._document_service.update_document(
                    doc_id,
                    status=DocumentStatus.COMPLETED,
                    chunk_count=len(children)
                )

                return IngestionResult(doc_id=doc_id, status=DocumentStatus.COMPLETED)

        except Exception as e:
            # В случае любой системной ошибки (база, сеть, память) ставим ERROR
            # Это позволит Celery сделать retry, если ошибка временная
            await self._document_service.update_document(
                doc_id,
                status=DocumentStatus.ERROR,
            )
            raise e

    async def index_vectors(self, childs: List[Dict[str, Any]]) -> List[List[float]]:
        """
        Performs batch vectorization of text chunks.

        Args:
            childs: List of chunk dictionaries containing 'text'.

        Returns:
            List[List[float]]: A list of generated embeddings.
        """
        texts = [str(child["text"]) for child in childs]
        return await self.vector_indexing_service.get_embeddings(texts)


    async def extract_and_store_chunks(self, doc_id: uuid.UUID, file_path: str) -> List[Dict]:
        """Runs the parsing pipeline and stores structural chunks in SQL."""
        parents, children = self._chunker.process(file_path)

        if not parents:
            raise ValueError("Extraction yielded no content.")

        await self._document_service.add_parent_chunks(doc_id, parents)
        return children

    @staticmethod
    def _compute_hash(file_bytes: bytes) -> str:
        """Computes SHA-256 hash for document content validation."""
        return hashlib.sha256(file_bytes).hexdigest()