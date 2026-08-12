from __future__ import annotations

from llm_service import infrastructure
from llm_service.LLM_provider import OpenAICompatLLMProvider


def test_selects_openrouter_provider(monkeypatch):
    monkeypatch.setattr(infrastructure.settings, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(infrastructure.settings, "OPENROUTER_API_KEY", "test-key")

    provider = infrastructure._build_llm_provider()

    assert isinstance(provider, OpenAICompatLLMProvider)
    assert provider._client.base_url == "https://openrouter.ai/api/v1/"


def test_selects_groq_provider(monkeypatch):
    monkeypatch.setattr(infrastructure.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(infrastructure.settings, "HF_TOKEN", "test-key")

    provider = infrastructure._build_llm_provider()

    assert isinstance(provider, OpenAICompatLLMProvider)
    assert provider._client.base_url == "https://router.huggingface.co/v1/"


def test_selects_openai_compat_provider_by_default(monkeypatch):
    monkeypatch.setattr(infrastructure.settings, "LLM_PROVIDER", "openai_compat")
    monkeypatch.setattr(infrastructure.settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(infrastructure.settings, "LLM_BASE_URL", "https://example.test/v1")

    provider = infrastructure._build_llm_provider()

    assert isinstance(provider, OpenAICompatLLMProvider)
    assert provider._client.base_url == "https://example.test/v1/"
