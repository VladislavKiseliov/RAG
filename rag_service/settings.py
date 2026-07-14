# rag_service/config.py
from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from rag_service.domain.storage import StorageDomain


class RagSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("rag_service/.env",".env"),  # ← ищет в обоих местах
        env_file_encoding="utf-8",
        extra="ignore",
    )

    MODE: Literal["DEV", "TEST", "PROD"]
    # ──────────────────────────────────────────
    # Database
    # ──────────────────────────────────────────
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    DB_NAME: str

    # ──────────────────────────────────────────
    # Test Database
    # ──────────────────────────────────────────

    TEST_DB_HOST: str
    TEST_DB_PORT: int
    TEST_DB_USER: str
    TEST_DB_PASS: str
    TEST_DB_NAME: str


    @property
    def DATABASE_URL(self)-> str:
        if self.MODE == "TEST":
            return f"postgresql+asyncpg://{self.TEST_DB_USER}:{self.TEST_DB_PASS}@{self.TEST_DB_HOST}:{self.TEST_DB_PORT}/{self.TEST_DB_NAME}"
        else:
            return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ──────────────────────────────────────────
    # Qdrant
    # ──────────────────────────────────────────
    qdrant_url: str                          # QDRANT_URL
    collection_name: str = "rag_documents_collection_with_sparse_vector"  # COLLECTION_NAME

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
    embedding_model_name: str
    embedding_batch_size: int = 64           # EMBEDDING_BATCH_SIZE

    # ──────────────────────────────────────────
    # Infrastructure
    # ──────────────────────────────────────────
    docs_directory: str = "./docs"           # DOCS_DIRECTORY
    qdrant_path: str = "./qdrant_storage"    # QDRANT_PATH
    redis_url: str = "redis://localhost:6379/0"  # REDIS_URL
    max_context_chars: int = 12000
    vector_timeout_seconds: float = 600.0

    # Upload validation
    upload_allowed_extensions: list[str] = [".pdf", ".docx", ".txt"]
    upload_max_size_bytes: int = 50 * 1024 * 1024  # 50 MB

    # ──────────────────────────────────────────
    # Docling conversion
    # ──────────────────────────────────────────
    docling_num_threads: int = 3
    docling_device: str = "cpu"  # cpu | cuda | mps | xpu | auto

    # Встроенный в Docling потоковый батчинг по страницам (StandardPdfPipeline) —
    # защита от переполнения памяти на больших PDF без ручного разрезания файла
    docling_ocr_batch_size: int = 4
    docling_layout_batch_size: int = 4
    docling_table_batch_size: int = 4
    docling_queue_max_size: int = 100
    docling_artifacts_path: str = "/root/.cache/docling/models"

    # MinIO
    minio_private_url: str
    minio_public_url:str
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool

    # MinIO buckets (по доменам)
    minio_bucket_knowledge_base: str
    minio_bucket_users: str
    minio_bucket_projects: str

    @property
    def minio_buckets(self) -> dict[StorageDomain, str]:
        return {
            StorageDomain.KNOWLEDGE_BASE: self.minio_bucket_knowledge_base,
            StorageDomain.USERS: self.minio_bucket_users,
            StorageDomain.PROJECTS: self.minio_bucket_projects,
        }
    # Redis
    redis_url:str


settings = RagSettings()