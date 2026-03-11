# infrastructure.py
from rag_service.db.session import create_engine, create_session_factory
from rag_service.providers.LLM_provider import GeminiLLMProvider
from rag_service.providers.hf_embedding_provider import HuggingFaceEmbeddingProvider
from rag_service.providers.minio_provider import MinioProvider
from rag_service.providers.qdrant_provider import QdrantVectorProvider
from rag_service.services.Retriver import SearchService
from rag_service.services.ingestion_service import IngestionService
from rag_service.settings import settings



def _build_minio_provider() -> MinioProvider:
    return MinioProvider(
        url=settings.minio_url,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
    )

def _build_embedding_provider():
    return HuggingFaceEmbeddingProvider(
        model=settings.embedding_model_name,
        token=settings.hf_token,
    )

def _build_vector_provider():

    return QdrantVectorProvider(
        url=settings.qdrant_url,
        collection=settings.collection_name,
        embedding_provider=_build_embedding_provider(),
        embedding_batch_size=settings.embedding_batch_size,
        upsert_batch_size=settings.qdrant_upsert_batch_size,
        hnsw_m=settings.qdrant_hnsw_m,
        hnsw_ef_construct=settings.qdrant_hnsw_ef_construct,
        optimizers_default_segment_number=settings.qdrant_optimizers_default_segment_number,
        optimizers_memmap_threshold=settings.qdrant_optimizers_memmap_threshold,
        optimizers_indexing_threshold=settings.qdrant_optimizers_indexing_threshold,
        wal_capacity_mb=settings.qdrant_wal_capacity_mb,
    )

def _build_llm_provider():
    if settings.llm_provider == "groq":
        from rag_service.providers.LLM_provider import GroqLLMProvider
        return GroqLLMProvider(api_key=settings.groq_api_key, model=settings.llm_model_name)
    else:
        from rag_service.providers.LLM_provider import GeminiLLMProvider
        return GeminiLLMProvider(api_key=settings.gemini_api_key, model=settings.llm_model_name)

def build_rag_infrastructure():
    engine = create_engine(settings.rag_database_url)
    session_factory = create_session_factory(engine)
    vector_provider = _build_vector_provider()
    minio_provider = _build_minio_provider()
    llm_provider = _build_llm_provider()

    search_service = SearchService(
        session_factory=session_factory,
        vector_provider=vector_provider,
        llm_provider=llm_provider,
        max_context_chars=settings.max_context_chars,
    )
    ingestion_service = IngestionService(  # ← добавить
        session_factory=session_factory,
        vector_provider=vector_provider,
        minio_provider=minio_provider,
        vector_timeout_seconds=settings.vector_timeout_seconds,
    )
    return engine, search_service, ingestion_service,minio_provider