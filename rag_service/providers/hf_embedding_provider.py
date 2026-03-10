from __future__ import annotations

import os
from typing import Any

import httpx

from rag_service.providers.embedding_provider import EmbeddingProvider


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """Эмбеддинги через HuggingFace Inference API.

    Использует endpoint feature-extraction. Возвращает один вектор на входной текст.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        token: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._model = model or os.getenv("EMBEDDING_MODEL_NAME")
        self._token = token or os.getenv("HF_TOKEN")
        self._timeout = timeout

        if not self._model:
            raise RuntimeError("EMBEDDING_MODEL_NAME is not set")
        if not self._token:
            raise RuntimeError("HF_TOKEN is not set")

        # Preferred modern endpoint for HF Inference providers.
        self._router_url = f"https://router.huggingface.co/hf-inference/models/{self._model}"
        # Legacy endpoint kept as fallback for backward compatibility.
        self._legacy_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self._model}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self._token}"}
        payload = {"inputs": texts}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self._router_url, json=payload, headers=headers)
            if resp.status_code in {404, 410}:
                resp = await client.post(self._legacy_url, json=payload, headers=headers)
        resp.raise_for_status()

        data: Any = resp.json()

        # Возможные форматы:
        # 1) list[list[float]] -> уже pooled
        # 2) list[list[list[float]]] -> per-token, делаем mean pooling
        if not data:
            return []

        if isinstance(data, list) and isinstance(data[0], list):
            if data and data[0] and isinstance(data[0][0], (int, float)):
                return data  # type: ignore[return-value]

            if data and isinstance(data[0][0], list):
                pooled: list[list[float]] = []
                for item in data:
                    pooled.append(_mean_pool(item))
                return pooled

        raise RuntimeError("Unexpected embedding response format")


def _mean_pool(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    size = len(vectors[0])
    sums = [0.0] * size
    for vec in vectors:
        for i, val in enumerate(vec):
            sums[i] += float(val)
    return [v / len(vectors) for v in sums]