import json

import httpx
import pytest

from rag_service.infrastructures.providers.tei_embedding_provider import TeiEmbeddingProvider


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Подменяет транспорт всех httpx.AsyncClient, создаваемых внутри provider.embed()."""
    transport = httpx.MockTransport(handler)
    original_init = httpx.AsyncClient.__init__

    def patched_init(self: httpx.AsyncClient, *args, **kwargs) -> None:
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


@pytest.mark.asyncio
async def test_embed_returns_empty_for_empty_input() -> None:
    provider = TeiEmbeddingProvider(base_url="http://tei")

    result = await provider.embed([])

    assert result == []


@pytest.mark.asyncio
async def test_embed_posts_inputs_and_returns_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=[[0.1, 0.2], [0.3, 0.4]])

    _patch_transport(monkeypatch, handler)
    provider = TeiEmbeddingProvider(base_url="http://tei")

    result = await provider.embed(["как настроить ПЛК", "давление в системе"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"] == "http://tei/embed"
    assert captured["body"] == {
        "inputs": ["как настроить ПЛК", "давление в системе"],
        "normalize": True,
    }


@pytest.mark.asyncio
async def test_embed_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    _patch_transport(monkeypatch, handler)
    provider = TeiEmbeddingProvider(base_url="http://tei")

    with pytest.raises(httpx.HTTPStatusError):
        await provider.embed(["text"])