# rag_service/config.py
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class RagSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ──────────────────────────────────────────
    # Database
    # ──────────────────────────────────────────
    rag_database_url: str  # RAG_DATABASE_URL

    # ──────────────────────────────────────────
    # Qdrant
    # ──────────────────────────────────────────
    qdrant_url: str                          # QDRANT_URL
    collection_name: str = "rag_documents_collection"  # COLLECTION_NAME

    qdrant_upsert_batch_size: int = 64
    qdrant_hnsw_m: int | None = None
    qdrant_hnsw_ef_construct: int | None = None
    qdrant_optimizers_default_segment_number: int | None = None
    qdrant_optimizers_memmap_threshold: int | None = None
    qdrant_optimizers_indexing_threshold: int | None = None
    qdrant_wal_capacity_mb: int | None = None

    # ──────────────────────────────────────────
    # Embeddings
    # ──────────────────────────────────────────
    hf_token: str = ""                       # HF_TOKEN
    embedding_model_name: str = "BAAI/bge-m3"  # EMBEDDING_MODEL_NAME
    embedding_batch_size: int = 64           # EMBEDDING_BATCH_SIZE

    # ──────────────────────────────────────────
    # LLM
    # ──────────────────────────────────────────
    gemini_api_key: str = ""                 # GEMINI_API_KEY
    llm_model_name: str = "models/gemini-2.5-flash-lite"  # LLM_MODEL_NAME

    # ──────────────────────────────────────────
    # Infrastructure
    # ──────────────────────────────────────────
    docs_directory: str = "./docs"           # DOCS_DIRECTORY
    qdrant_path: str = "./qdrant_storage"    # QDRANT_PATH
    redis_url: str = "redis://localhost:6379/0"  # REDIS_URL
    max_context_chars: int = 12000
    vector_timeout_seconds: float = 60.0


settings = RagSettings()