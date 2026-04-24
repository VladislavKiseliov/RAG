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

from rag_service.infrastructures.providers.embedding_provider import EmbeddingProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorProvider


class QdrantVectorStorage():
    """Qdrant-backed vector storage adapter.

    Responsibility boundary:
    - stores already prepared vectors with payload,
    - performs similarity search in Qdrant,
    - deletes document-scoped points,
    - ensures the target collection exists.

    What this provider does not own anymore:
    - embedding orchestration for ingestion batches,
    - batching source texts for embedding generation,
    - building application-level point payloads from document chunks.

    Those responsibilities now belong to the application layer
    (`VectorIndexingService`, `IngestionService`).
    """

    def __init__(
        self,
        *,
        url: str,
        collection: str,
        embedding_provider: EmbeddingProvider,
        distance: str = "Cosine",
        upsert_batch_size: int = 64,
        hnsw_m: int | None = None,
        hnsw_ef_construct: int | None = None,
        optimizers_default_segment_number: int | None = None,
        optimizers_memmap_threshold: int | None = None,
        optimizers_indexing_threshold: int | None = None,
        wal_capacity_mb: int | None = None,
    ) -> None:
        """Create a Qdrant storage adapter.

        Args:
            url: Qdrant base URL.
            collection: Target Qdrant collection name.
            embedding_provider: Provider used only for query embedding during search.
                Ingestion-time embeddings are prepared outside this class.
            distance: Vector distance metric name understood by Qdrant.
            upsert_batch_size: Maximum number of ready vector points sent per upsert call.
            hnsw_m: Optional HNSW graph connectivity parameter.
            hnsw_ef_construct: Optional HNSW build quality parameter.
            optimizers_default_segment_number: Optional Qdrant optimizer setting.
            optimizers_memmap_threshold: Optional Qdrant optimizer setting.
            optimizers_indexing_threshold: Optional Qdrant optimizer setting.
            wal_capacity_mb: Optional write-ahead log capacity.
        """
        if not url:
            raise RuntimeError("QDRANT_URL is not set")
        if not collection:
            raise RuntimeError("COLLECTION_NAME is not set")

        self._client = AsyncQdrantClient(url=url)
        self._collection = collection
        self._embedding_provider = embedding_provider
        self._distance = Distance[distance.upper()]
        self._upsert_batch_size = max(1, upsert_batch_size)
        self._hnsw_m = hnsw_m
        self._hnsw_ef_construct = hnsw_ef_construct
        self._optimizers_default_segment_number = optimizers_default_segment_number
        self._optimizers_memmap_threshold = optimizers_memmap_threshold
        self._optimizers_indexing_threshold = optimizers_indexing_threshold
        self._wal_capacity_mb = wal_capacity_mb

    async def upsert_vectors(self, points: list[dict]) -> None:
        """Persist already-vectorized points in Qdrant.

        Expected point format:
            {
                "id": <optional int | UUID | str>,
                "vector": list[float],
                "payload": dict,
            }

        Notes:
        - The provider assumes vectors are already computed.
        - Payload is stored as-is after shallow copying.
        - Upserts are split into Qdrant-sized batches only.
        """
        if not points:
            return

        first_vector = points[0].get("vector")
        if not first_vector:
            raise RuntimeError("Point vector is empty")

        await self._ensure_collection(len(first_vector))

        for start in range(0, len(points), self._upsert_batch_size):
            batch = points[start : start + self._upsert_batch_size]
            qdrant_points: list[PointStruct] = []
            for index, point in enumerate(batch, start=start):
                point_id = self._normalize_point_id(point.get("id"), fallback=f"point:{index}")
                qdrant_points.append(
                    PointStruct(
                        id=point_id,
                        vector=point["vector"],
                        payload=dict(point.get("payload") or {}),
                    )
                )

            await self._client.upsert(
                collection_name=self._collection,
                points=qdrant_points,
                wait=True,
            )

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        doc_id: uuid.UUID | None = None,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """Search nearest stored chunks by text query.

        Search flow:
        1. normalize and validate the text query,
        2. embed the query text into one vector,
        3. execute Qdrant vector search,
        4. optionally filter by one document,
        5. return lightweight hits with `id`, `score`, and `payload`.

        This method still owns query embedding because retrieval currently uses
        a text-first contract at the provider boundary.
        """
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

        results = await self._client.query_points(
            collection_name=self._collection,
            query=vectors[0],
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
            for r in results.points
        ]

    async def delete(self, doc_id: uuid.UUID) -> None:
        """Delete every vector point that belongs to one document.

        Document ownership is resolved by payload field `doc_id`.
        """
        await self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))]
            ),
            wait=True,
        )

    async def _ensure_collection(self, vector_size: int) -> None:
        """Create the target collection lazily if it does not exist yet.

        The collection schema is derived from the first upserted vector size
        and the configured distance/index optimizer settings.
        """
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
        """Convert an arbitrary application point id into a Qdrant-supported id.

        Qdrant supports integer ids and UUID-like string ids.
        This helper accepts several application-level forms and normalizes them to:
        - `int` for purely numeric ids,
        - canonical UUID string when possible,
        - deterministic UUID5 string fallback for arbitrary text/object ids.
        """
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
