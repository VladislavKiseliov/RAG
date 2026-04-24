from __future__ import annotations

from rag_service.infrastructures.providers.embedding_provider import EmbeddingProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorProvider


class VectorIndexingService:
    """Embeds point texts and sends ready vectors to the vector store."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_provider: VectorProvider,
        embedding_batch_size: int = 64,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_provider = vector_provider
        self._embedding_batch_size = max(1, embedding_batch_size)

    async def upsert_points(self, points: list[dict]) -> None:
        if not points:
            return

        texts = [str(point.get("text", "")) for point in points]
        if any(not text.strip() for text in texts):
            raise RuntimeError("Point text is empty")

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._embedding_batch_size):
            batch = texts[start : start + self._embedding_batch_size]
            batch_vectors = await self._embedding_provider.embed(batch)
            if not batch_vectors:
                raise RuntimeError("Embeddings are empty")
            vectors.extend(batch_vectors)

        ready_points = []
        for point, vector in zip(points, vectors, strict=True):
            payload = dict(point.get("payload") or {})
            payload.setdefault("text", point["text"])
            ready_points.append(
                {
                    "id": point.get("id"),
                    "vector": vector,
                    "payload": payload,
                }
            )

        await self._vector_provider.upsert_vectors(ready_points)
