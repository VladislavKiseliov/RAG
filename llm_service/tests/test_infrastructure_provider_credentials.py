from __future__ import annotations

import pytest

from llm_service import infrastructure


def test_raises_on_empty_openrouter_api_key(monkeypatch):
    monkeypatch.setattr(infrastructure.settings, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(infrastructure.settings, "OPENROUTER_API_KEY", "")

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        infrastructure._build_llm_provider()


def test_constructs_with_non_empty_openrouter_api_key(monkeypatch):
    monkeypatch.setattr(infrastructure.settings, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(infrastructure.settings, "OPENROUTER_API_KEY", "test-key")

    provider = infrastructure._build_llm_provider()

    assert provider._client.base_url == "https://openrouter.ai/api/v1/"


def test_raises_on_empty_groq_api_key(monkeypatch):
    monkeypatch.setattr(infrastructure.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(infrastructure.settings, "HF_TOKEN", "")

    with pytest.raises(ValueError, match="HF_TOKEN"):
        infrastructure._build_llm_provider()


def test_raises_on_empty_openai_compat_api_key(monkeypatch):
    monkeypatch.setattr(infrastructure.settings, "LLM_PROVIDER", "openai_compat")
    monkeypatch.setattr(infrastructure.settings, "LLM_API_KEY", "")
    monkeypatch.setattr(infrastructure.settings, "LLM_BASE_URL", "https://example.test/v1")

    with pytest.raises(ValueError, match="LLM_API_KEY"):
        infrastructure._build_llm_provider()
