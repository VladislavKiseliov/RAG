from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("llm_service/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    LLM_API_KEY: str
    LLM_BASE_URL: str

    HF_TOKEN: str = ""
    OPENROUTER_API_KEY: str = ""
    LLM_PROVIDER: str = "openai_compat"

    RAG_SERVICE_URL: str
    LLM_RAG_TIMEOUT: float
    LLM_MAX_CONTEXT_CHARS: int

    RERANKER_TEI_URL: str
    LLM_RERANK_TIMEOUT: float = 30.0


settings = LLMSettings()
