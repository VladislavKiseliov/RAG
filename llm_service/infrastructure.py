from __future__ import annotations

import os

from llm_service.application.answer_service import AnswerService
from llm_service.application.rag_client import RagClient
from llm_service.LLM_provider import LLMProvider, OpenAICompatLLMProvider, _get_api_key


def _build_llm_provider() -> LLMProvider:
    api_key = _get_api_key()
    base_url = os.getenv("LLM_BASE_URL", "https://gatellm.ru/v1")
    model = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    return OpenAICompatLLMProvider(api_key=api_key, base_url=base_url, model=model)


def build_answer_service() -> AnswerService:
    rag_url = os.getenv("RAG_SERVICE_URL", "http://rag_service:8001")
    timeout = float(os.getenv("LLM_RAG_TIMEOUT", "30"))
    max_context_chars = int(os.getenv("LLM_MAX_CONTEXT_CHARS", "12000"))

    rag_client = RagClient(base_url=rag_url, timeout=timeout)
    llm_provider = _build_llm_provider()
    return AnswerService(
        rag_client=rag_client,
        llm_provider=llm_provider,
        max_context_chars=max_context_chars,
    )
