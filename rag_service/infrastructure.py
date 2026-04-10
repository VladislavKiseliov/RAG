from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from rag_service.application.document_service import DocumentQueryService, DocumentService
from rag_service.application.ingestion_service import IngestionService
from rag_service.application.retrieve_service import RetrieveService
from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.infrastructures.db.session import create_engine, create_session_factory
from rag_service.infrastructures.providers.hf_embedding_provider import HuggingFaceEmbeddingProvider
from rag_service.infrastructures.providers.minio_provider import MinioProvider
from rag_service.infrastructures.providers.qdrant_provider import QdrantVectorProvider
from rag_service.settings import settings


# ---------------- Контейнеры ----------------

@dataclass(frozen=True)
class RagContainer:
    engine: AsyncEngine
    retrieve_service: RetrieveService
    document_service: DocumentService
    document_query_service: DocumentQueryService
    ingestion_service: IngestionService
    minio_provider: MinioProvider


@dataclass(frozen=True)
class WorkerContainer:
    ingestion_service: IngestionService
    minio_provider: MinioProvider


# ---------------- Внутренняя общая часть ----------------

@dataclass(frozen=True)
class _SharedInfrastructure:
    vector_provider: QdrantVectorProvider
    vector_indexing_service: VectorIndexingService
    minio_provider: MinioProvider
    document_service: DocumentService


def _build_minio_provider() -> MinioProvider:
    return MinioProvider(
        url=settings.minio_url,
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


def _build_vector_provider(embedding_provider: HuggingFaceEmbeddingProvider) -> QdrantVectorProvider:
    return QdrantVectorProvider(
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


def _build_shared_infrastructure(
    session_factory: async_sessionmaker[AsyncSession],
) -> _SharedInfrastructure:
    embedding_provider = _build_embedding_provider()
    vector_provider = _build_vector_provider(embedding_provider)
    vector_indexing_service = VectorIndexingService(
        embedding_provider=embedding_provider,
        vector_provider=vector_provider,
        embedding_batch_size=settings.embedding_batch_size,
    )
    return _SharedInfrastructure(
        vector_provider=vector_provider,
        vector_indexing_service=vector_indexing_service,
        minio_provider=_build_minio_provider(),
        document_service=DocumentService(session_factory),
    )


def _build_ingestion_service(shared: _SharedInfrastructure) -> IngestionService:
    return IngestionService(
        document_service=shared.document_service,
        vector_provider=shared.vector_provider,
        vector_indexing_service=shared.vector_indexing_service,
        minio_provider=shared.minio_provider,
        vector_timeout_seconds=settings.vector_timeout_seconds,
    )


# ---------------- Публичные билдеры ----------------

def build_rag_infrastructure() -> RagContainer:
    engine = create_engine(settings.rag_database_url)
    sf = create_session_factory(engine)
    shared = _build_shared_infrastructure(sf)
    document_query_service = DocumentQueryService(sf)

    return RagContainer(
        engine=engine,
        retrieve_service=RetrieveService(
            session_factory=sf,
            vector_provider=shared.vector_provider,
            document_service=document_query_service,
        ),
        document_service=shared.document_service,
        document_query_service=document_query_service,
        ingestion_service=_build_ingestion_service(shared),
        minio_provider=shared.minio_provider,
    )


def build_worker_infrastructure() -> WorkerContainer:
    engine = create_engine(settings.rag_database_url)
    sf = create_session_factory(engine)
    shared = _build_shared_infrastructure(sf)

    return WorkerContainer(
        ingestion_service=_build_ingestion_service(shared),
        minio_provider=shared.minio_provider,
    )