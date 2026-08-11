from __future__ import annotations

from llm_service import infrastructure
from llm_service.LLM_provider import GroqLLMProvider, OpenAICompatLLMProvider, OpenRouterLLMProvider


def test_selects_openrouter_provider(monkeypatch):
    monkeypatch.setattr(infrastructure.settings, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(infrastructure.settings, "OPENROUTER_API_KEY", "test-key")

    provider = infrastructure._build_llm_provider()

    assert isinstance(provider, OpenRouterLLMProvider)


def test_selects_groq_provider(monkeypatch):
    monkeypatch.setattr(infrastructure.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(infrastructure.settings, "HF_TOKEN", "test-key")

    provider = infrastructure._build_llm_provider()

    assert isinstance(provider, GroqLLMProvider)


def test_selects_openai_compat_provider_by_default(monkeypatch):
    monkeypatch.setattr(infrastructure.settings, "LLM_PROVIDER", "openai_compat")
    monkeypatch.setattr(infrastructure.settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(infrastructure.settings, "LLM_BASE_URL", "https://example.test/v1")

    provider = infrastructure._build_llm_provider()

    assert isinstance(provider, OpenAICompatLLMProvider)
