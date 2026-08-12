from __future__ import annotations

import pytest
from pydantic import ValidationError

from llm_service.settings import LLMSettings

_REQUIRED_KWARGS = dict(
    LLM_API_KEY="test-key",
    LLM_BASE_URL="https://example.test/v1",
    RAG_SERVICE_URL="http://rag-service:8001",
    LLM_RAG_TIMEOUT=30.0,
    LLM_MAX_CONTEXT_CHARS=12000,
    RERANKER_TEI_URL="http://tei-reranker:80",
)


def test_rejects_invalid_llm_provider_value():
    with pytest.raises(ValidationError, match="openai_compat"):
        LLMSettings(_env_file=None, LLM_PROVIDER="openroute", **_REQUIRED_KWARGS)


@pytest.mark.parametrize("provider", ["openai_compat", "groq", "openrouter"])
def test_accepts_each_valid_llm_provider_value(provider):
    settings = LLMSettings(_env_file=None, LLM_PROVIDER=provider, **_REQUIRED_KWARGS)
    assert settings.LLM_PROVIDER == provider


def test_default_llm_provider_is_unchanged_openrouter():
    settings = LLMSettings(_env_file=None, **_REQUIRED_KWARGS)
    assert settings.LLM_PROVIDER == "openrouter"
