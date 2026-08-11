from __future__ import annotations

import pytest

from llm_service.LLM_provider import OpenRouterLLMProvider


def test_raises_on_empty_api_key():
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        OpenRouterLLMProvider(api_key="")


def test_constructs_with_non_empty_api_key():
    provider = OpenRouterLLMProvider(api_key="test-key")
    assert provider._client.base_url == "https://openrouter.ai/api/v1/"
