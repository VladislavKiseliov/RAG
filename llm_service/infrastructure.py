from __future__ import annotations

from dataclasses import dataclass


from llm_service.application.lean_rag_agent import LeanRagAgent
from llm_service.application.services.reranker_service import RerankerService
from llm_service.application.services.retrieval_service import RetrievalService
from llm_service.LLM_provider import LLMProvider, OpenAICompatLLMProvider
from llm_service.settings import settings
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.infrastructure")


@dataclass(frozen=True)
class LLMContainer:
    agent: LeanRagAgent


@dataclass(frozen=True)
class _ProviderConfig:
    base_url: str
    api_key: str
    key_name: str  # for the error message only


def _resolve_provider_config() -> _ProviderConfig:
    if settings.LLM_PROVIDER == "groq":
        return _ProviderConfig("https://router.huggingface.co/v1", settings.HF_TOKEN, "HF_TOKEN")
    if settings.LLM_PROVIDER == "openrouter":
        return _ProviderConfig("https://openrouter.ai/api/v1", settings.OPENROUTER_API_KEY, "OPENROUTER_API_KEY")
    return _ProviderConfig(settings.LLM_BASE_URL, settings.LLM_API_KEY, "LLM_API_KEY")


def _build_llm_provider() -> LLMProvider:
    config = _resolve_provider_config()
    if not config.api_key:
        raise ValueError(f"{config.key_name} is not set")
    return OpenAICompatLLMProvider(api_key=config.api_key, base_url=config.base_url)


def build_rag_client() -> RetrievalService:
    return RetrievalService(
        base_url=settings.RAG_SERVICE_URL,
        timeout=settings.LLM_RAG_TIMEOUT,
    )


def build_reranker_client() -> RerankerService:
    return RerankerService(
        base_url=settings.RERANKER_TEI_URL,
        timeout=settings.LLM_RERANK_TIMEOUT,
    )


def build_container() -> LLMContainer:
    retrieve_service = build_rag_client()
    llm_provider = _build_llm_provider()
    agent = LeanRagAgent(llm_provider = llm_provider,
                        retrieval_service=retrieve_service,
                        reranker_service=build_reranker_client(),
                        )
    return LLMContainer(agent=agent)