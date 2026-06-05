"""Local embeddings via sentence-transformers."""

from __future__ import annotations

import asyncio
import os

from sentence_transformers import SentenceTransformer

from rag_service.infrastructures.providers.embedding_provider import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    """Embedding provider that runs locally without external API calls."""

    def __init__(self, *, model: str | None = None) -> None:
        self._model_name = model or os.getenv("EMBEDDING_MODEL_NAME")
        self._model = SentenceTransformer(self._model_name)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Encode texts into embedding vectors asynchronously."""
        if not texts:
            return []
        vectors = await asyncio.to_thread(
            self._model.encode,
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return [vec.tolist() for vec in vectors]

