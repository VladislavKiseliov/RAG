"""Эмбеддинги через Text Embeddings Inference (TEI) — HTTP."""

from __future__ import annotations

import httpx

from rag_service.infrastructures.providers.embedding_provider import EmbeddingProvider


class TeiEmbeddingProvider(EmbeddingProvider):
    """Эмбеддинги через self-hosted TEI (`POST /embed`).

    TEI отдаёт уже пуленные вектора (list[list[float]]) — в отличие от сырого
    HF Inference API, дополнительный mean pooling на клиенте не нужен.
    """

    def __init__(self, *, base_url: str, timeout: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/embed",
                json={"inputs": texts, "normalize": True},
            )
        resp.raise_for_status()
        return resp.json()