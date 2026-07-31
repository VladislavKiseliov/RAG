import json

import httpx
import pytest

from llm_service.ml_router.tei_embedder import TeiSyncEmbedder


def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """Подменяет транспорт всех httpx.Client, создаваемых внутри embedder.encode()."""
    transport = httpx.MockTransport(handler)
    original_init = httpx.Client.__init__

    def patched_init(self: httpx.Client, *args, **kwargs) -> None:
        kwargs["transport"] = transport
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "__init__", patched_init)


def test_encode_posts_inputs_without_prefix_and_returns_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=[[0.1, 0.2]])

    _patch_transport(monkeypatch, handler)
    embedder = TeiSyncEmbedder(base_url="http://tei")

    result = embedder.encode(["как настроить ПЛК"], normalize_embeddings=True)

    assert result == [[0.1, 0.2]]
    assert captured["url"] == "http://tei/embed"
    # Без "query: "-префикса - train.py обучал классификатор на сыром тексте.
    assert captured["body"] == {"inputs": ["как настроить ПЛК"], "normalize": True}


def test_encode_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    _patch_transport(monkeypatch, handler)
    embedder = TeiSyncEmbedder(base_url="http://tei")

    with pytest.raises(httpx.HTTPStatusError):
        embedder.encode(["text"])