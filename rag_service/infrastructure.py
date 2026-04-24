from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from rag_service.application.document_service import DocumentService
from rag_service.infrastructures.providers.s3_storage_provider import S3StorageProvider
from rag_service.workers.ingestion_service import IngestionService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository
from rag_service.infrastructures.db.session import create_engine, create_session_factory
from rag_service.infrastructures.providers.hf_embedding_provider import HuggingFaceEmbeddingProvider
from rag_service.infrastructures.providers.minio_provider import MinioProvider
from rag_service.domain.qdrant_vector_storage import QdrantVectorStorage
from rag_service.settings import settings


# ---------------- Контейнеры ----------------

@dataclass(frozen=True)
class RagContainer:

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    s3_storage: S3StorageRepository
    vector_storage : QdrantVectorStorage


@dataclass(frozen=True)
class WorkerContainer:
    ingestion_service: IngestionService
    minio_provider: MinioProvider


# ---------------- Внутренняя общая часть ----------------

@dataclass(frozen=True)
class _SharedInfrastructure:
    vector_provider: QdrantVectorStorage
    vector_indexing_service: VectorIndexingService
    minio_provider: MinioProvider
    document_service: DocumentService


def _build_s3_storage() -> S3StorageProvider:
    return S3StorageRepository(
        endpoint_url=settings.minio_url,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
    )


def _build_embedding_provider() -> HuggingFaceEmbeddingProvider:
    return HuggingFaceEmbeddingProvider(
        model=settings.embedding_model_name,
        token=settings.hf_token,
    )


def _build_vector_storage(embedding_provider: HuggingFaceEmbeddingProvider) -> QdrantVectorStorage:
    return QdrantVectorStorage(
        url=settings.qdrant_url,
        collection=settings.collection_name,
        embedding_provider=embedding_provider,
        upsert_batch_size=settings.qdrant_upsert_batch_size,
        hnsw_m=settings.qdrant_hnsw_m,
        hnsw_ef_construct=settings.qdrant_hnsw_ef_construct,
        optimizers_default_segment_number=settings.qdrant_optimizers_default_segment_number,
        optimizers_memmap_threshold=settings.qdrant_optimizers_memmap_threshold,
        optimizers_indexing_threshold=settings.qdrant_optimizers_indexing_threshold,
        wal_capacity_mb=settings.qdrant_wal_capacity_mb,
    )


# def _build_shared_infrastructure(
#     session_factory: async_sessionmaker[AsyncSession],
# ) -> _SharedInfrastructure:
#     embedding_provider = _build_embedding_provider()
#     vector_provider = _build_vector_storage(embedding_provider)
#     vector_indexing_service = VectorIndexingService(
#         embedding_provider=embedding_provider,
#         vector_provider=vector_provider,
#         embedding_batch_size=settings.embedding_batch_size,
#     )
#     return _SharedInfrastructure(
#         vector_provider=vector_provider,
#         vector_indexing_service=vector_indexing_service,
#         minio_provider=_build_minio_provider(),
#         document_service=DocumentService(session_factory),
#     )


def _build_ingestion_service(shared: _SharedInfrastructure) -> IngestionService:
    return IngestionService(
        document_service=shared.document_service,
        vector_provider=shared.vector_provider,
        vector_indexing_service=shared.vector_indexing_service,
        s3_storage=shared.minio_provider,
        vector_timeout_seconds=settings.vector_timeout_seconds,
    )


# ---------------- Публичные билдеры ----------------

def build_rag_infrastructure() -> RagContainer:
    engine = create_engine(settings.rag_database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    embedding_provider = _build_embedding_provider()
    vector_storage = _build_vector_storage(embedding_provider)
    s3_storage = _build_s3_storage()

    return RagContainer(
        engine=engine,
        session_factory = session_factory,
        s3_storage = s3_storage,
        vector_storage = vector_storage,
    )


def build_worker_infrastructure() -> WorkerContainer:
    engine = create_engine(settings.rag_database_url)
    sf = create_session_factory(engine)
    shared = _build_shared_infrastructure(sf)

    return WorkerContainer(
        ingestion_service=_build_ingestion_service(shared),
        minio_provider=shared.minio_provider,
    )