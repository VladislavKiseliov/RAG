from __future__ import annotations

from functools import lru_cache
import os

from llm_service.application.agent_service import LlmLangGraphAgent
from llm_service.application.answer_service import AnswerService
from llm_service.application.rag_client import RagClient
from llm_service.infrastructure import _build_llm_provider, build_answer_service


@lru_cache(maxsize=1)
def get_answer_service() -> AnswerService:
    return build_answer_service()


@lru_cache(maxsize=1)
def get_langgraph_agent() -> LlmLangGraphAgent:
    rag_url = os.getenv("RAG_SERVICE_URL", "http://rag_service:8001")
    timeout = float(os.getenv("LLM_RAG_TIMEOUT", "30"))
    rag_client = RagClient(base_url=rag_url, timeout=timeout)
    llm_provider = _build_llm_provider()
    return LlmLangGraphAgent(llm_provider=llm_provider, rag_client=rag_client)
