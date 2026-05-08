from __future__ import annotations

import os
from dataclasses import dataclass

from llm_service.application.agent_service import LlmLangGraphAgent
from llm_service.application.answer_service import AnswerService
from llm_service.application.rag_client import RagClient
from llm_service.LLM_provider import LLMProvider, OpenAICompatLLMProvider, _get_api_key




@dataclass(frozen=True)
class LLMContainer:
    """Контейнер для основного API приложения."""
    answer_service: AnswerService



def _build_llm_provider() -> LLMProvider:
    base_url = os.getenv("LLM_BASE_URL", "https://gatellm.ru/v1")
    model = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    return OpenAICompatLLMProvider(base_url=base_url, model=model)


def build_answer_service() -> AnswerService:
    rag_url = os.getenv("RAG_SERVICE_URL", "http://rag_service:8001")
    timeout = float(os.getenv("LLM_RAG_TIMEOUT", "30"))
    max_context_chars = int(os.getenv("LLM_MAX_CONTEXT_CHARS", "12000"))

    rag_client = RagClient(base_url=rag_url, timeout=timeout)
    llm_provider = _build_llm_provider()
    answer_service = AnswerService(
        rag_client=rag_client,
        llm_provider=llm_provider,
        max_context_chars=max_context_chars,
    )
    return LLMContainer(
        answer_service=answer_service
    )