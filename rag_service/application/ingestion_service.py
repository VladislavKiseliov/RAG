from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict
import hashlib

from sqlalchemy.exc import DBAPIError, OperationalError

from rag_service.domain.errors.base import DuplicateFileError, InvalidIngestionStateError
from rag_service.domain.errors.storage import StorageDeleteError, StorageReadError, StorageWriteError
from rag_service.domain.errors.vector import VectorUpsertError
from rag_service.domain.models.vector_point import VectorPoint

logger = logging.getLogger(__name__)

from rag_service.application.docling_pipeline import DocumentConversionPipeline
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.domain.chunking.docling_models import ParsedDocument
from rag_service.domain.chunking.chunk_builder import ChildChunkBuilder
from rag_service.domain.chunking.chunk_builder import ChunkDeduplicator
from rag_service.domain.chunking.chunk_builder import ContentFilter
from rag_service.domain.chunking.chunk_builder import ParentChunk
from rag_service.domain.document import IngestionDocument

from rag_service.infrastructures.providers.bucket_storage_provider import BucketStorageProvider
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
            s3_storage: BucketStorageProvider,
            conversion_pipeline: DocumentConversionPipeline,
    ) -> None:
        """
        Initializes the IngestionService with required providers.

        Args:
            document_service: Service for SQL database operations.
            vector_storage: Provider for vector database operations.
            vector_indexing_service: Service for generating text embeddings.
            s3_storage: Provider for file storage (S3/Minio).
            conversion_pipeline: Converts PDF into markdown + chapters + tables (Docling).
        """
        self._document_service = document_service
        self.vector_storage = vector_storage
        self.vector_indexing_service = vector_indexing_service
        self.s3_storage = s3_storage
        self._conversion_pipeline = conversion_pipeline
        self._filter = ContentFilter()
        self._deduplicator = ChunkDeduplicator()
        self._child_builder = ChildChunkBuilder()

    async def process_document(self, doc_id: uuid.UUID, s3key: str) -> IngestionResult:
        """Полный цикл обработки документа: скачивание → чанкинг → векторизация → Qdrant.

        Политика ошибок:
            - `DuplicateFileError` — файл с таким хешем уже есть, удаляем эту запись сразу
              (ещё ничего не записано, кроме исходного PDF), не ретраим.
            - `StorageReadError`/`StorageWriteError`/`StorageDeleteError`/`VectorUpsertError`/
              `OperationalError`/`DBAPIError` — транзиентные инфраструктурные сбои (сеть,
              S3, Qdrant, БД) — пробрасываем наружу, Celery ретраит (см. `workers/task.py`).
            - `ValueError`/`InvalidIngestionStateError` — детерминированная ошибка (пустой/
              битый PDF, нарушение порядка стадий) — ретрай не поможет, статус ERROR.
            - Всё остальное (неизвестная ошибка) — по умолчанию тоже не ретраим: безопаснее
              один раз пометить ERROR и разобраться, чем молча повторять баг.
            Во всех "не ретраим" случаях, кроме дубликата, документ не удаляется сразу —
            только помечается ERROR (см. `_schedule_delayed_cleanup`, пока заглушка).
        """
        # 1. ЗАГРУЖАЕМ существующий документ из БД, чтобы не потерять file_size и метаданные
        db_doc = await self._document_service.get_document_by_id(doc_id)
        if not db_doc:
            raise ValueError(f"Document {doc_id} targets ghost record in database.")

        file_name = Path(s3key).name
        doc = IngestionDocument(
            id=db_doc.id,
            filename=db_doc.filename,
            s3key=db_doc.s3key,
            file_size=db_doc.file_size,
            status=DocumentStatus.PENDING
        )
        logger.info("Starting ingestion doc_id=%s s3key=%s", doc_id, s3key)

        try:
            # ШАГ 1: Скачивание и проверка на дубликаты
            async with self._lifecycle_step(doc):
                doc.start_processing()
                file_bytes, file_hash = await self._download_and_validate_hashes(doc_id=doc_id, s3key=s3key)
                doc.file_hash = file_hash

            async with self._lifecycle_step(doc):
                doc.start_extraction()

            # ШАГ 2: Извлечение сырых данных (Docling)
            parsed_document = self._extract_raw_content(file_bytes, file_name)

            # ШАГ 3: Получение чанков по тексту
            parent_chunks, children_chunks = self.store_chunks(parsed_document, file_name)

            # ШАГ 3б: Сохранение структуры в SQL (Главы, Таблицы)
            await self._store_structural_data(doc_id, parent_chunks, parsed_document)

            # ШАГ 4: Индексация в векторной базе (Qdrant)
            async with self._lifecycle_step(doc):
                doc.start_indexing()
                await self._run_pipeline(doc_id, children_chunks)

            # ШАГ 5: Финализация
            async with self._lifecycle_step(doc):
                doc.complete(len(children_chunks))
                logger.info("Ingestion completed doc_id=%s chunks=%d", doc_id, doc.chunk_count)

            return IngestionResult(doc_id=doc_id, status=doc.status)

        except DuplicateFileError as e:
            # Файл с таким хешем уже есть — чистим за собой сразу, ретрай бессмысленен
            logger.info("Duplicate detected doc_id=%s file_hash=%s: %s", doc_id, e.file_hash, e.message)
            doc.mark_duplicate()
            await self._document_service.delete_document(doc_id)
            await self.s3_storage.delete_file(s3key)
            return IngestionResult(doc_id=doc_id, status=doc.status)

        except (StorageReadError, StorageWriteError, StorageDeleteError, VectorUpsertError,
                OperationalError, DBAPIError) as e:
            # Транзиентная инфраструктура (S3, Qdrant, БД) — статус не трогаем,
            # Celery ретраит саму задачу (см. workers/task.py)
            logger.warning("Transient infrastructure error doc_id=%s: %s", doc_id, e)
            raise

        except (ValueError, InvalidIngestionStateError) as e:
            # Детерминированная ошибка (пустой/битый PDF, нарушение порядка стадий) —
            # ретрай не поможет, тот же файл сломается точно так же
            logger.error("Non-retryable ingestion error doc_id=%s: %s", doc_id, e)
            doc.fail()
            await self._document_service.update_document(doc_id, update_data={"status": doc.status})
            self._schedule_delayed_cleanup(doc_id)
            return IngestionResult(doc_id=doc_id, status=doc.status)

        except Exception as e:
            # Неизвестная ошибка — по умолчанию не ретраим: безопаснее один раз
            # пометить ERROR и разобраться, чем молча повторять баг три раза
            logger.exception("Unhandled ingestion error doc_id=%s", doc_id)
            doc.fail()
            await self._document_service.update_document(doc_id, update_data={"status": doc.status})
            self._schedule_delayed_cleanup(doc_id)
            return IngestionResult(doc_id=doc_id, status=doc.status)

    def _schedule_delayed_cleanup(self, doc_id: uuid.UUID) -> None:
        """Планирует отложенное удаление документа со статусом ERROR (через пару часов).

        TODO: пока заглушка. Реализация — отдельный Celery-таск
        (`apply_async(countdown=...)`), который проверит, что статус всё ещё
        ERROR (не был исправлен вручную), и вызовет `delete_document()`.
        Здесь пока только фиксируем намерение в логах.
        """
        logger.warning("TODO: delayed cleanup not implemented yet, doc_id=%s stays ERROR", doc_id)



    async def _download_and_validate_hashes(
            self,
            doc_id: uuid.UUID,
            s3key: str
        )-> tuple[bytes, str]:

        # 1. Скачиваем файл из S3
        file_bytes = await self.s3_storage.get_file(s3key)

        # 2. Вычисляем SHA-256 хеш и переходит в PROCESSING
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        logger.debug("Hash computed doc_id=%s hash=%s", doc_id, file_hash)

        # 3. Проверка дубликата: ищем документ с таким же хешем в БД
        existing = await self._document_service.get_document_by_hash(file_hash)

        if existing is not None and existing.id != doc_id:
            logger.info("Duplicate detected doc_id=%s existing_id=%s", doc_id, existing.id)
            raise DuplicateFileError(file_hash)

        return file_bytes, file_hash

    async def delete_document(
            self,
            doc_id:uuid.UUID,
            s3key:str
    ):
        await self._document_service.delete_document(doc_id)
        await self.s3_storage.delete_file(s3key)

    @asynccontextmanager
    async def _lifecycle_step(self, doc: IngestionDocument):
        """
        Контекстный менеджер для автоматической синхронизации
        статуса и метаданных документа с БД при смене этапа.
        """
        try:
            yield
        finally:
            full_dict = asdict(doc)
            exclude_fields = {"id", "filename", "s3key"}
            update_data = {
                k: v for k, v in full_dict.items()
                if v is not None and k not in exclude_fields
            }
            logger.debug("Syncing document state to DB: status=%s", doc.status)
            await self._document_service.update_document(
                doc_id=doc.id,
                update_data=update_data,
            )

    async def _run_pipeline(self, doc_id: uuid.UUID, children: List[Dict], batch_size: int = 25) -> None:
        semaphore = asyncio.Semaphore(3)
        background_tasks = set()

        async def process_batch_chain(batch_data: List[Dict]):
            async with semaphore:
                batch_texts = [str(c["text"]) for c in batch_data]

                dense_vectors, sparse_vectors = await self.vector_indexing_service.get_hybrid_vectors(batch_texts)

                ready_point = self._creates_points(doc_id=doc_id,
                                     childs=batch_data,
                                     dense_vectors=dense_vectors,
                                     sparse_vectors=sparse_vectors
                                     )

                await self.vector_storage.upsert_vectors(ready_point)

        for start in range(0, len(children), batch_size):
            batch = children[start: start + batch_size]

            task = asyncio.create_task(process_batch_chain(batch))

            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

        if background_tasks:
            await asyncio.gather(*background_tasks)


    def store_chunks(self,parse_document:ParsedDocument,file_name:str) -> tuple[list[ParentChunk], list[Dict]]:
        """Строит parent/child chunks из глав документа (фильтрация, дедупликация, нарезка)."""

        parents, children = self._build_chunks(parse_document, source=file_name)

        if not parents:
            raise ValueError("Extraction yielded no content.")

        return parents, children


    async def _store_structural_data(
            self,
            doc_id,
            parent_chunks: List[ParentChunk],
            parsed_document:ParsedDocument,
    )->None:

        await self._document_service.add_parent_chunks(doc_id,parent_chunks)
        await self._store_docling_artifacts(doc_id, parsed_document)



    def _extract_raw_content(self, content: bytes, filename: str) -> ParsedDocument:
        """Конвертирует PDF в markdown + главы + таблицы через Docling (см. DocumentConversionPipeline)."""
        return self._conversion_pipeline.convert_document(content, filename)

    def _build_chunks(self, docling_result: ParsedDocument, source: str) -> tuple[List[ParentChunk], List[Dict]]:
        """Строит parent/child chunks из глав документа: фильтрация шума, дедупликация, нарезка."""
        self._deduplicator.reset()

        parents: List[ParentChunk] = []
        children: List[Dict] = []

        for index, chapter in enumerate(docling_result.chapters):
            text = chapter.markdown
            headers = {"chapter_number": chapter.number, "title": chapter.title}

            if self._filter.should_skip(text):
                continue

            if self._deduplicator.is_duplicate(text):
                continue

            parent = ParentChunk(
                text=text,
                headers=headers,
                source=source,
                doc_index=index,
            )
            parents.append(parent)

            for child_chunk in self._child_builder.build(text):
                children.append(
                    {
                        "id": None,
                        "parent_id": parent.id,
                        "text": child_chunk.text,
                        "headers": headers,
                        "source": source,
                    }
                )

        return parents, children

    async def _store_docling_artifacts(self, doc_id: uuid.UUID, docling_result: ParsedDocument) -> None:
        """Заливает в S3 сырые артефакты Docling про запас: полный текст, главы, таблицы, мета-разделы."""
        prefix = str(doc_id)

        await self.s3_storage.upload_file(
            docling_result.full_markdown.encode("utf-8"), f"{prefix}/full.md", "text/markdown"
        )

        for chapter in docling_result.chapters:
            safe_num = chapter.number.replace(".", "_")
            await self.s3_storage.upload_file(
                chapter.markdown.encode("utf-8"), f"{prefix}/chapters/chapter_{safe_num}.md", "text/markdown"
            )

        for table in docling_result.tables:
            await self.s3_storage.upload_file(
                table.csv_bytes, f"{prefix}/tables/table_{table.index}.csv", "text/csv"
            )
            await self.s3_storage.upload_file(
                table.html_bytes, f"{prefix}/tables/table_{table.index}.html", "text/html"
            )

        for section in docling_result.meta_sections:
            name = section.section_type.lower()
            await self.s3_storage.upload_file(
                section.markdown.encode("utf-8"), f"{prefix}/meta/{name}.md", "text/markdown"
            )


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