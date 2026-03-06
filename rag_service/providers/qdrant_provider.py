from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    OptimizersConfigDiff,
    PointStruct,
    VectorParams,
    WalConfigDiff,
)

from rag_service.providers.embedding_provider import EmbeddingProvider
from rag_service.providers.vector_provider import VectorProvider


class QdrantVectorProvider(VectorProvider):
    """Запись и поиск векторов в Qdrant через официальный async клиент."""

    def __init__(
        self,
        *,
        url: str,
        collection: str,
        embedding_provider: EmbeddingProvider,
        distance: str = "Cosine",
        embedding_batch_size: int = 64,
        upsert_batch_size: int = 64,
        hnsw_m: int | None = None,
        hnsw_ef_construct: int | None = None,
        optimizers_default_segment_number: int | None = None,
        optimizers_memmap_threshold: int | None = None,
        optimizers_indexing_threshold: int | None = None,
        wal_capacity_mb: int | None = None,
    ) -> None:
        if not url:
            raise RuntimeError("QDRANT_URL is not set")
        if not collection:
            raise RuntimeError("COLLECTION_NAME is not set")

        self._client = AsyncQdrantClient(url=url) # HTTP клиент для общения с Qdrant. Один экземпляр на весь провайдер.
        self._collection = collection  # Имя коллекции в Qdrant
        self._embedding_provider = embedding_provider  # Провайдер эмбеддингов (HuggingFace, OpenAI и т.д.).
        # Метрика расстояния между векторами.
        # Distance.COSINE — угол между векторами (стандарт для текста).
        # Distance.DOT — скалярное произведение.
        # Distance.EUCLID — евклидово расстояние.
        self._distance = Distance[distance.upper()]

        self._embedding_batch_size = max(1, embedding_batch_size) # Сколько текстов отправляем в embedding_provider за один запрос.
        self._upsert_batch_size = max(1, upsert_batch_size) # Сколько точек отправляем в Qdrant за один upsert запрос.
        self._hnsw_m = hnsw_m # Количество связей у каждой точки в HNSW графе.
        self._hnsw_ef_construct = hnsw_ef_construct # Качество построения HNSW графа при индексации.
        self._optimizers_default_segment_number = optimizers_default_segment_number # Количество сегментов коллекции.
        self._optimizers_memmap_threshold = optimizers_memmap_threshold # Порог в килобайтах после которого сегмент переносится на диск (mmap).
        self._optimizers_indexing_threshold = optimizers_indexing_threshold # Порог в килобайтах после которого строится HNSW индекс для сегмента.
        self._wal_capacity_mb = wal_capacity_mb # Размер WAL (Write-Ahead Log) в мегабайтах.

    async def upsert_with_payload(self, doc_id: uuid.UUID, points: list[dict]) -> None:
        """Генерирует эмбеддинги и записывает точки с произвольным payload."""
        if not points:
            return

        texts = [str(point.get("text", "")) for point in points]
        if any(not text.strip() for text in texts):
            raise RuntimeError("Point text is empty")

        # Генерируем эмбеддинги батчами
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._embedding_batch_size):
            batch = texts[start : start + self._embedding_batch_size]
            batch_vectors = await self._embedding_provider.embed(batch)
            if not batch_vectors:
                raise RuntimeError("Embeddings are empty")
            vectors.extend(batch_vectors)

        await self._ensure_collection(len(vectors[0]))

        # Upsert батчами
        for start in range(0, len(points), self._upsert_batch_size):
            end = start + self._upsert_batch_size
            batch_points = []

            for idx, (point, vector) in enumerate(
                zip(points[start:end], vectors[start:end]), start=start
            ):
                payload = dict(point.get("payload") or {})
                payload.setdefault("doc_id", str(doc_id))
                payload.setdefault("text", point["text"])
                point_id = self._normalize_point_id(point.get("id"), fallback=f"{doc_id}:{idx}")

                batch_points.append(PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                ))

            await self._client.upsert(
                collection_name=self._collection,
                points=batch_points,
                wait=True,
            )

    async def upsert(self, doc_id: uuid.UUID, chunks: list[str], meta: dict | None) -> None:
        """Совместимый upsert: преобразует список строк в точки с payload."""
        points = []
        for idx, chunk in enumerate(chunks):
            payload: dict[str, Any] = {"doc_id": str(doc_id), "chunk_index": idx, "text": chunk}
            if meta:
                payload["meta"] = meta
            points.append({"id": f"{doc_id}:{idx}", "text": chunk, "payload": payload})
        await self.upsert_with_payload(doc_id, points)

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        doc_id: uuid.UUID | None = None,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """Поиск ближайших чанков по текстовому запросу."""
        clean_query = query.strip()
        if not clean_query:
            return []

        vectors = await self._embedding_provider.embed([clean_query])
        if not vectors:
            return []

        query_filter = None
        if doc_id is not None:
            query_filter = Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))]
            )

        results = await self._client.search(
            collection_name=self._collection,
            query_vector=vectors[0],
            limit=max(1, top_k),
            score_threshold=score_threshold,
            query_filter=query_filter,
            with_payload=True,
            with_vectors=False,
        )

        return [
            {
                "id": r.id,
                "score": float(r.score),
                "payload": r.payload or {},
            }
            for r in results
        ]

    async def delete(self, doc_id: uuid.UUID) -> None:
        """Удаляет все точки документа из коллекции по payload.doc_id."""
        await self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))]
            ),
            wait=True,
        )

    async def _ensure_collection(self, vector_size: int) -> None:
        """Проверяет существование коллекции и создаёт при отсутствии."""
        exists = await self._client.collection_exists(self._collection)
        if exists:
            return

        hnsw_config = None
        if self._hnsw_m is not None or self._hnsw_ef_construct is not None:
            hnsw_config = HnswConfigDiff(
                m=self._hnsw_m,
                ef_construct=self._hnsw_ef_construct,
            )

        optimizers_config = None
        if any(v is not None for v in [
            self._optimizers_default_segment_number,
            self._optimizers_memmap_threshold,
            self._optimizers_indexing_threshold,
        ]):
            optimizers_config = OptimizersConfigDiff(
                default_segment_number=self._optimizers_default_segment_number,
                memmap_threshold=self._optimizers_memmap_threshold,
                indexing_threshold=self._optimizers_indexing_threshold,
            )

        wal_config = None
        if self._wal_capacity_mb is not None:
            wal_config = WalConfigDiff(wal_capacity_mb=self._wal_capacity_mb)

        await self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams(size=vector_size, distance=self._distance),
            hnsw_config=hnsw_config,
            optimizers_config=optimizers_config,
            wal_config=wal_config,
        )

    @staticmethod
    def _normalize_point_id(raw_id: Any, *, fallback: str) -> str | int:
        """Конвертирует id точки в тип поддерживаемый Qdrant: int или UUID строка."""
        candidate = raw_id if raw_id is not None else fallback
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, uuid.UUID):
            return str(candidate)
        if isinstance(candidate, str):
            text = candidate.strip()
            if text.isdigit():
                return int(text)
            try:
                return str(uuid.UUID(text))
            except ValueError:
                return str(uuid.uuid5(uuid.NAMESPACE_URL, text))
        return str(uuid.uuid5(uuid.NAMESPACE_URL, str(candidate)))