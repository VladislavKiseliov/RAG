from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import  Optional

from qdrant_client import AsyncQdrantClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

# Импорты сервисов и провайдеров
#
# ВАЖНО: этот модуль импортируется rag_service.main (API-процесс, лёгкий образ без
# Docling/torch/CUDA - см. Dockerfile stage `base`). Всё, что тянет Docling
# (DocumentConversionPipeline, IngestionService, DoclingConversionRepository) - в
# rag_service/worker_container.py, который импортирует только rag_service.workers.task
# (тяжёлый образ, stage `worker`). Не добавляйте сюда Docling-импорты обратно.
from rag_service.application.abbreviation_expander import AbbreviationExpander
from rag_service.application.document_service import DocumentQueryService
from rag_service.application.s3_service.knowledge_base_storage import KnowledgeBaseStorageService
from rag_service.infrastructures.repositories.qdrant_vector_storage import QdrantVectorStorage
from rag_service.infrastructures.providers.bucket_storage_provider import BucketStorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository
from rag_service.infrastructures.providers.tei_embedding_provider import TeiEmbeddingProvider
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
    abbreviation_expander: AbbreviationExpander


# WorkerContainer/build_worker_infrastructure - см. rag_service/worker_container.py
# (нужны только rag_service.workers.task, тяжёлому Celery-воркеру)


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
_v_indexing_service_lock = threading.Lock()

def get_v_indexing_service() -> VectorIndexingService:
    global v_indexing_service
    if v_indexing_service is None:
        with _v_indexing_service_lock:
            if v_indexing_service is None:
                emb_provider = TeiEmbeddingProvider(base_url=settings.tei_url)
                sparse_provider = BM25EmbeddingService()
                v_indexing_service = VectorIndexingService(
                    embedding_provider=emb_provider,
                    sparse_provider=sparse_provider,
                )
    return v_indexing_service


async def _build_abbreviation_expander(session_factory: async_sessionmaker[AsyncSession]) -> AbbreviationExpander:
    """Загружает весь словарь аббревиатур один раз при старте процесса.

    Таблица маленькая (максимум пара сотен строк на реальный корпус) - вместо
    Redis pub/sub-инвалидации между процессами (см. целевую архитектуру в
    ISSUES.md A11) держим её в памяти без реализации перезагрузки; новые
    аббревиатуры из документов, проиндексированных после старта, подхватятся
    только после рестарта API-процесса.
    """
    rows = await DocumentQueryService(session_factory).get_all_abbreviations()
    return AbbreviationExpander.from_pairs((row.acronym, row.expansion) for row in rows)


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
    abbreviation_expander = await _build_abbreviation_expander(session_factory)

    return RagContainer(
        engine=engine,
        session_factory=session_factory,
        s3_storage=s3_store,
        vector_storage=v_storage,
        notes_vector_storage=notes_v_storage,
        v_indexing_service = v_indexing_service,
        abbreviation_expander=abbreviation_expander,
    )