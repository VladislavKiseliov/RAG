from __future__ import annotations

from dataclasses import dataclass
from typing import  Optional

from qdrant_client import AsyncQdrantClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

# Импорты сервисов и провайдеров
from docling.datamodel.accelerator_options import AcceleratorDevice

from rag_service.application.docling_pipeline import DocumentConversionPipeline
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.application.s3_service.knowledge_base_storage import KnowledgeBaseStorageService
from rag_service.infrastructures.providers.pdf_conversion_provider import PdfConversionProvider
from rag_service.infrastructures.repositories.docling_conversion_repository import DoclingConversionRepository
from rag_service.infrastructures.repositories.qdrant_vector_storage import QdrantVectorStorage
from rag_service.infrastructures.providers.bucket_storage_provider import BucketStorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider
from rag_service.application.ingestion_service import IngestionService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository
from rag_service.infrastructures.repositories.local_embedding_repository import LocalEmbeddingProvider
from rag_service.infrastructures.repositories.bm25_embedding_service import BM25EmbeddingService
from rag_service.settings import settings


# ---------------- Контейнеры (Data Classes) ----------------

@dataclass(frozen=True)
class RagContainer:
    """Контейнер для основного API приложения."""
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    s3_storage: BucketStorageProvider
    vector_storage: VectorStorageProvider
    notes_vector_storage: VectorStorageProvider
    v_indexing_service:VectorIndexingService


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


# ---------------- Вспомогательные Билдеры ----------------

def _create_db_factory(database_url: str, pool_size: int = 5):
    # Настраиваем движок с учетом пула соединений
    engine = create_async_engine(
        database_url,
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    return engine, session_factory


def _build_s3_store() -> S3StorageRepository:
    return S3StorageRepository(
        private_endpoint_url=settings.minio_private_url,
        public_endpoint_url=settings.minio_public_url,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def _build_knowledge_base_storage() -> BucketStorageProvider:
    return KnowledgeBaseStorageService(store=_build_s3_store())

v_indexing_service: Optional[VectorIndexingService] = None

def get_v_indexing_service() -> VectorIndexingService:
    global v_indexing_service
    if v_indexing_service is None:
        emb_provider = LocalEmbeddingProvider(model=settings.embedding_model_name)
        sparse_provider = BM25EmbeddingService()
        v_indexing_service = VectorIndexingService(
            embedding_provider=emb_provider,
            sparse_provider=sparse_provider,
        )
    return v_indexing_service


docling_conversion_provider: Optional[PdfConversionProvider] = None

def get_docling_conversion_provider() -> PdfConversionProvider:
    """Синглтон: Docling грузит OCR-модели при инициализации, пересоздавать на каждую задачу дорого."""
    global docling_conversion_provider
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


def _build_qdrant_client() -> AsyncQdrantClient:
    if not settings.qdrant_url:
        raise RuntimeError("QDRANT_URL is not set")
    return AsyncQdrantClient(url=settings.qdrant_url, timeout=60)


def _build_vector_storage(client: AsyncQdrantClient, collection: str) -> VectorStorageProvider:
    """Один Qdrant-клиент, разные коллекции — см. QdrantVectorStorage."""
    return QdrantVectorStorage(
        client=client,
        collection=collection,
        upsert_batch_size=settings.qdrant_upsert_batch_size,
        hnsw_m=settings.qdrant_hnsw_m,
        hnsw_ef_construct=settings.qdrant_hnsw_ef_construct,
        optimizers_default_segment_number=settings.qdrant_optimizers_default_segment_number,
        optimizers_memmap_threshold=settings.qdrant_optimizers_memmap_threshold,
        optimizers_indexing_threshold=settings.qdrant_optimizers_indexing_threshold,
        wal_capacity_mb=settings.qdrant_wal_capacity_mb,

    )


# ---------------- Публичные методы инициализации ----------------

async def build_rag_infrastructure(db_pool_size: int = 10) -> RagContainer:
    """Создает инфраструктуру для FastAPI."""
    engine, session_factory = _create_db_factory(settings.DATABASE_URL, pool_size=db_pool_size)
    v_indexing_service = get_v_indexing_service()
    qdrant_client = _build_qdrant_client()
    v_storage = _build_vector_storage(qdrant_client, settings.collection_name)
    notes_v_storage = _build_vector_storage(qdrant_client, settings.notes_collection_name)
    s3_store = _build_knowledge_base_storage()
    await s3_store.ensure_bucket()

    return RagContainer(
        engine=engine,
        session_factory=session_factory,
        s3_storage=s3_store,
        vector_storage=v_storage,
        notes_vector_storage=notes_v_storage,
        v_indexing_service = v_indexing_service,
    )


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