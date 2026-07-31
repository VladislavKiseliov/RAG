from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from docling.datamodel.accelerator_options import AcceleratorDevice

from rag_service.application.docling_pipeline import DocumentConversionPipeline
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.application.ingestion_service import IngestionService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.container import (
    _build_knowledge_base_storage,
    _build_qdrant_client,
    _build_vector_storage,
    _create_db_factory,
    get_v_indexing_service,
)
from rag_service.infrastructures.providers.bucket_storage_provider import BucketStorageProvider
from rag_service.infrastructures.providers.pdf_conversion_provider import PdfConversionProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider
from rag_service.infrastructures.repositories.docling_conversion_repository import DoclingConversionRepository
from rag_service.settings import settings


@dataclass(frozen=True)
class WorkerContainer:
    """Контейнер для воркера Celery (включает IngestionService)."""
    ingestion_service: IngestionService
    document_service: DataBaseDocumentService
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    s3_storage: BucketStorageProvider
    vector_storage: VectorStorageProvider
    notes_vector_storage: VectorStorageProvider
    v_indexing_service: VectorIndexingService


docling_conversion_provider: Optional[PdfConversionProvider] = None
_docling_conversion_provider_lock = threading.Lock()


def get_docling_conversion_provider() -> PdfConversionProvider:
    """Синглтон: Docling грузит OCR-модели при инициализации, пересоздавать на каждую задачу дорого.

    Безопасно под текущим Celery prefork pool (отдельные процессы, не делят этот global),
    но double-checked locking на случай перехода на threads/eventlet/gevent — тот же паттерн,
    что get_v_indexing_service в container.py (см. A6 в ISSUES.md).
    """
    global docling_conversion_provider
    if docling_conversion_provider is None:
        with _docling_conversion_provider_lock:
            if docling_conversion_provider is None:
                docling_conversion_provider = DoclingConversionRepository(
                    num_threads=settings.docling_num_threads,
                    device=AcceleratorDevice(settings.docling_device),
                    ocr_batch_size=settings.docling_ocr_batch_size,
                    layout_batch_size=settings.docling_layout_batch_size,
                    table_batch_size=settings.docling_table_batch_size,
                    queue_max_size=settings.docling_queue_max_size,
                    artifacts_path=settings.docling_artifacts_path,
                )
    return docling_conversion_provider


async def build_worker_infrastructure() -> WorkerContainer:
    """Создает инфраструктуру для воркера Celery."""
    # Для воркера пул маленький, так как один процесс обрабатывает одну задачу
    engine, session_factory = _create_db_factory(settings.DATABASE_URL, pool_size=2)

    # 1. Слой данных
    doc_service = DataBaseDocumentService(session_factory=session_factory)
    s3_store = _build_knowledge_base_storage()
    await s3_store.ensure_bucket()

    # 2. Слой векторов (делим один провайдер эмбеддингов и один Qdrant-клиент между сервисами)
    v_indexing_service = get_v_indexing_service()
    qdrant_client = _build_qdrant_client()
    v_storage = _build_vector_storage(qdrant_client, settings.collection_name)
    notes_v_storage = _build_vector_storage(qdrant_client, settings.notes_collection_name)

    # 3. Оркестратор обработки (Ingestion)
    ing_service = IngestionService(
        document_service=doc_service,
        vector_storage=v_storage,
        vector_indexing_service=v_indexing_service,
        s3_storage=s3_store,
        conversion_pipeline=DocumentConversionPipeline(provider=get_docling_conversion_provider()),
    )

    return WorkerContainer(
        ingestion_service=ing_service,
        document_service=doc_service,
        engine=engine,
        session_factory=session_factory,
        s3_storage=s3_store,
        vector_storage=v_storage,
        notes_vector_storage=notes_v_storage,
        v_indexing_service=v_indexing_service,
    )