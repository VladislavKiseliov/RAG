# backend/config.py
from typing import Literal

from pydantic_settings import BaseSettings,SettingsConfigDict


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),  # ← ищет в обоих местах
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
    # Authentication
    # ──────────────────────────────────────────
    SECRET_KEY  :str
    ALGORITHM   :str
    ACCESS_TOKEN_EXPIRE_MINUTES :int
    REFRESH_TOKEN_EXPIRE_DAYS   :int

    # MinIO
    MINIO_URL: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str
    MINIO_SECURE: bool

    # Internal services
    LLM_SERVICE_URL: str = "http://llm-service:8002"
    RAG_SERVICE_URL: str = "http://rag-service:8001"
    FLOWER_URL: str = "http://flower:5555"


settings = BackendSettings()
