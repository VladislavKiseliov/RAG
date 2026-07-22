"""Local embeddings via sentence-transformers."""

from __future__ import annotations

import asyncio
import os

import torch
from sentence_transformers import SentenceTransformer

from rag_service.infrastructures.providers.embedding_provider import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    """Embedding provider that runs locally without external API calls."""

    def __init__(self, *, model: str | None = None, batch_size: int = 32) -> None:
        self._model_name = model or os.getenv("EMBEDDING_MODEL_NAME")
        self._batch_size = batch_size
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        model_kwargs = {"torch_dtype": torch.float16} if self._device == "cuda" else {}
        self._model = SentenceTransformer(self._model_name, device=self._device, model_kwargs=model_kwargs)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = await asyncio.to_thread(
            self._model.encode,
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        if self._device == "cuda":
            torch.cuda.empty_cache()
        return [vec.tolist() for vec in vectors]