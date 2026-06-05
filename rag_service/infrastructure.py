from __future__ import annotations

from dataclasses import dataclass
from typing import  Optional

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

# Импорты сервисов и провайдеров
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.infrastructures.repositories.qdrant_vector_storage import QdrantVectorStorage
from rag_service.infrastructures.providers.s3_storage_provider import S3StorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider
from rag_service.workers.ingestion_service import IngestionService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository
from rag_service.infrastructures.repositories.local_embedding_reposittory import LocalEmbeddingProvider
from rag_service.infrastructures.repositories.bm25_embedding_service import BM25EmbeddingService
from rag_service.settings import settings


# ---------------- Контейнеры (Data Classes) ----------------

@dataclass(frozen=True)
class RagContainer:
    """Контейнер для основного API приложения."""
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    s3_storage: S3StorageProvider
    vector_storage: VectorStorageProvider
    v_indexing_service:VectorIndexingService


@dataclass(frozen=True)
class WorkerContainer:
    """Контейнер для воркера Celery (включает IngestionService)."""
    ingestion_service: IngestionService
    document_service: DataBaseDocumentService
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    s3_storage: S3StorageProvider
    vector_storage: VectorStorageProvider


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


def _build_s3_storage() -> S3StorageProvider:
    return S3StorageRepository(
        private_endpoint_url=settings.minio_private_url,
        public_endpoint_url=settings.minio_public_url,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
    )

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



def _build_vector_storage() -> VectorStorageProvider:
    return QdrantVectorStorage(
        url=settings.qdrant_url,
        collection=settings.collection_name,
        upsert_batch_size=settings.qdrant_upsert_batch_size,
        hnsw_m=settings.qdrant_hnsw_m,
        hnsw_ef_construct=settings.qdrant_hnsw_ef_construct,
        optimizers_default_segment_number=settings.qdrant_optimizers_default_segment_number,
        optimizers_memmap_threshold=settings.qdrant_optimizers_memmap_threshold,
        optimizers_indexing_threshold=settings.qdrant_optimizers_indexing_threshold,
        wal_capacity_mb=settings.qdrant_wal_capacity_mb,

    )


# ---------------- Публичные методы инициализации ----------------

def build_rag_infrastructure(db_pool_size: int = 10) -> RagContainer:
    """Создает инфраструктуру для FastAPI."""
    engine, session_factory = _create_db_factory(settings.DATABASE_URL, pool_size=db_pool_size)
    v_indexing_service = get_v_indexing_service()
    v_storage = _build_vector_storage()
    s3_store = _build_s3_storage()

    return RagContainer(
        engine=engine,
        session_factory=session_factory,
        s3_storage=s3_store,
        vector_storage=v_storage,
        v_indexing_service = v_indexing_service,
    )


def build_worker_infrastructure() -> WorkerContainer:
    """Создает инфраструктуру для воркера Celery."""
    # Для воркера пул маленький, так как один процесс обрабатывает одну задачу
    engine, session_factory = _create_db_factory(settings.DATABASE_URL, pool_size=2)

    # 1. Слой данных
    doc_service = DataBaseDocumentService(session_factory=session_factory)
    s3_store = _build_s3_storage()

    # 2. Слой векторов (делим один провайдер эмбеддингов между сервисами)
    v_indexing_service = get_v_indexing_service()
    v_storage = _build_vector_storage()


    # 3. Оркестратор обработки (Ingestion)
    ing_service = IngestionService(
        document_service=doc_service,
        vector_storage=v_storage,
        vector_indexing_service=v_indexing_service,
        s3_storage=s3_store,
    )

    return WorkerContainer(
        ingestion_service=ing_service,
        document_service=doc_service,
        engine=engine,
        session_factory=session_factory,
        s3_storage=s3_store,
        vector_storage=v_storage
    )

