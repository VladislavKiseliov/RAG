from __future__ import annotations

import asyncio
import logging
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict

from rag_service.domain.models.vector_point import VectorPoint

logger = logging.getLogger(__name__)

from rag_service.application.chunking_pipeline import DocumentChunkingPipeline
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.domain.document import IngestionDocument

from rag_service.infrastructures.providers.s3_storage_provider import S3StorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider
from rag_service.models import DocumentStatus


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
        self._chunker = DocumentChunkingPipeline()

    async def process_document(self, doc_id: uuid.UUID, s3key: str) -> IngestionResult:
        """Полный цикл обработки документа: скачивание → чанкинг → векторизация → Qdrant.

        Raises:
            ValueError: PDF пустой или не распарсился — ретрай бессмысленен.
            Exception: Сетевые/инфраструктурные ошибки — Celery сделает retry.
        """
        # 1. ЗАГРУЖАЕМ существующий документ из БД, чтобы не потерять file_size и метаданные
        db_doc = await self._document_service.get_document_by_id(doc_id)
        if not db_doc:
            raise ValueError(f"Document {doc_id} targets ghost record in database.")

        file_name = Path(s3key).name
        doc = IngestionDocument(
            id=db_doc.id,
            filename=db_doc.filename,
            s3_key=db_doc.s3key,
            file_size=db_doc.file_size,
            status=DocumentStatus.PENDING
        )
        logger.info("Starting ingestion doc_id=%s s3key=%s", doc_id, s3key)

        try:
            # 1. Скачиваем файл из S3
            file_bytes = await self.s3_storage.get_file(s3key)

            # 2. Домен вычисляет SHA-256 хеш и переходит в PROCESSING
            doc.start_processing(file_bytes)
            logger.debug("Hash computed doc_id=%s hash=%s", doc_id, doc.file_hash)

            # 3. Проверка дубликата: ищем документ с таким же хешем в БД
            existing = await self._document_service.get_document_by_hash(doc.file_hash)
            if existing is not None and existing.id != doc_id:
                logger.info("Duplicate detected doc_id=%s existing_id=%s", doc_id, existing.id)
                doc.mark_duplicate()
                await self._document_service.delete_document(doc_id)
                await self.s3_storage.delete_file(s3key)
                return IngestionResult(doc_id=doc_id, status=doc.status)

            # 4. Сохраняем хеш и статус PROCESSING в БД
            await self._document_service.update_document(
                doc_id, status=doc.status, file_hash=doc.file_hash
            )

            # 5. Парсим файл во временной директории
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir) / file_name
                tmp_path.write_bytes(file_bytes)

                doc.start_extraction()
                await self._document_service.update_document(doc_id, status=doc.status)

                children = await self.extract_and_store_chunks(doc_id, str(tmp_path))
                logger.info("Extraction done doc_id=%s chunks=%d", doc_id, len(children))

                # 6. Векторизация батчами + параллельная запись в Qdrant
                doc.start_indexing()
                await self._document_service.update_document(doc_id, status=doc.status)

                await self._run_pipeline(doc_id, children)

                # 7. Финализация
                doc.complete(len(children))
                await self._document_service.update_document(
                    doc_id, status=doc.status, chunk_count=doc.chunk_count
                )
                logger.info("Ingestion completed doc_id=%s chunks=%d", doc_id, doc.chunk_count)

                return IngestionResult(doc_id=doc_id, status=doc.status)

        except ValueError as e:
            # Пустой PDF или невалидный контент — ретрай не поможет
            logger.error("Extraction failed doc_id=%s error=%s", doc_id, e)
            doc.fail()
            await self._document_service.update_document(doc_id, status=doc.status)
            return IngestionResult(doc_id=doc_id, status=doc.status)

        except Exception as e:
            # Остальные инфраструктурные ошибки (S3, БД, сеть) — Celery ретраит
            logger.exception("Ingestion error doc_id=%s", doc_id)
            doc.fail()
            await self._document_service.update_document(doc_id, status=doc.status)
            raise e


    async def _run_pipeline(self, doc_id: uuid.UUID, children: List[Dict], batch_size: int = 50) -> None:
        semaphore = asyncio.Semaphore(4)
        background_tasks = set()

        async def process_batch_chain(batch_data: List[Dict]):
            batch_texts = [str(c["text"]) for c in batch_data]

            dense_vectors, sparse_vectors = await self.vector_indexing_service.get_hybrid_vectors(batch_texts)

            ready_point = self._creates_points(doc_id=doc_id,
                                 childs=batch_data,
                                 dense_vectors=dense_vectors,
                                 sparse_vectors=sparse_vectors
                                 )

            async with semaphore:
                await self.vector_storage.upsert_vectors(ready_point)

        for start in range(0, len(children), batch_size):
            batch = children[start: start + batch_size]

            task = asyncio.create_task(process_batch_chain(batch))

            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

        if background_tasks:
            await asyncio.gather(*background_tasks)


    async def extract_and_store_chunks(self, doc_id: uuid.UUID, file_path: str) -> List[Dict]:
        """Runs the parsing pipeline and stores structural chunks in SQL."""
        parents, children = self._chunker.process(file_path)

        if not parents:
            raise ValueError("Extraction yielded no content.")

        await self._document_service.add_parent_chunks(doc_id, parents)
        return children


    def _creates_points(self,doc_id: uuid.UUID, childs: list,dense_vectors:list[list[float]],sparse_vectors) -> list[VectorPoint]:
        """
                Internal mapper that assembles the dictionary structure for Qdrant points.

                This method ensures that the 'text' and 'doc_id' are always present
                in the point's payload for efficient retrieval and filtering.
                """
        if not childs or not dense_vectors or not sparse_vectors:
            return []

        ready_points = []

        for child, dense_vector, sparse_vector in zip(childs, dense_vectors, sparse_vectors, strict=True):
            point_id = child.get("id") or str(uuid.uuid4())


            point = VectorPoint(
                id=point_id,
                dense_vector=dense_vector,
                sparse_vector=sparse_vector,
                text=child["text"],
                payload={
                    "parent_id": child["parent_id"],
                    "headers": child.get("headers") or {},
                    "text": child["text"],
                    "source": child.get("source", ""),
                    "doc_id": str(doc_id),
                }
            )
            ready_points.append(point)
        return ready_points





