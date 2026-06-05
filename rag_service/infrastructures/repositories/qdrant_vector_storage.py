from __future__ import annotations

import asyncio
import uuid

from typing import Any, List

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.models import FilterSelector
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    OptimizersConfigDiff,
    PointStruct,
    QueryRequest,
    SparseVector,
    VectorParams,
    WalConfigDiff,
    Document,
)

from rag_service.domain.errors.vector import (
    VectorCollectionError,
    VectorDeleteError,
    VectorSearchError,
    VectorSearchInputError,
    VectorUpsertError,
)
from rag_service.domain.models.vector_point import VectorPoint


class QdrantVectorStorage():
    """Qdrant-backed vector storage adapter.

    Implements VectorStorageProvider over AsyncQdrantClient.
    Hybrid search (dense + BM25 sparse) with configurable fusion strategy.
    Collection is created lazily on first upsert.
    """

    def __init__(
        self,
        *,
        url: str,
        collection: str,
        distance: str = "Cosine",
        upsert_batch_size: int = 64,
        hnsw_m: int | None = None,
        hnsw_ef_construct: int | None = None,
        optimizers_default_segment_number: int | None = None,
        optimizers_memmap_threshold: int | None = None,
        optimizers_indexing_threshold: int | None = None,
        wal_capacity_mb: int | None = None,
    ) -> None:
        """
        Args:
            url: Qdrant base URL.
            collection: Target collection name.
            fusion: Hybrid search fusion strategy (DBSF or RRF). Default: DBSF.
            distance: Vector distance metric. Default: Cosine.
            upsert_batch_size: Points per upsert batch.
            hnsw_m: HNSW graph connectivity parameter.
            hnsw_ef_construct: HNSW build quality parameter.
            optimizers_default_segment_number: Qdrant optimizer setting.
            optimizers_memmap_threshold: Qdrant optimizer setting.
            optimizers_indexing_threshold: Qdrant optimizer setting.
            wal_capacity_mb: Write-ahead log capacity.
        """
        if not url:
            raise RuntimeError("QDRANT_URL is not set")
        if not collection:
            raise RuntimeError("COLLECTION_NAME is not set")

        self._client: AsyncQdrantClient = AsyncQdrantClient(url=url)
        self._collection = collection
        self._collection_lock = asyncio.Lock()
        self._fusion = models.Fusion.DBSF
        self.bm25_model = "qdrant/bm25"
        self._distance = Distance[distance.upper()]
        self._upsert_batch_size = max(1, upsert_batch_size)
        self._hnsw_m = hnsw_m
        self._hnsw_ef_construct = hnsw_ef_construct
        self._optimizers_default_segment_number = optimizers_default_segment_number
        self._optimizers_memmap_threshold = optimizers_memmap_threshold
        self._optimizers_indexing_threshold = optimizers_indexing_threshold
        self._wal_capacity_mb = wal_capacity_mb

    async def upsert_vectors(self, points: List[VectorPoint]) -> None:
        """Сохраняет уже векторизованные доменные точки в Qdrant.

        Принимает готовый батч точек, проверяет/создает коллекцию
        и отправляет данные в Qdrant без повторного разбиения.
        """
        if not points:
            return

        vector_size = len(points[0].dense_vector)
        if not vector_size:
            raise RuntimeError("Point dense vector is empty")

        try:
            await self._ensure_collection(vector_size)

            qdrant_points: list[PointStruct] = []
            for index, point in enumerate(points):
                point_id = self._normalize_point_id(point.id, fallback=f"point:{index}")
                qdrant_points.append(
                    PointStruct(
                        id=point_id,
                        vector={
                            "dense_vector": point.dense_vector,
                            "bm25_sparse_vector": SparseVector(
                                indices=point.sparse_vector.indices,
                                values=point.sparse_vector.values
                            )
                        },
                        payload=point.payload,
                    )
                )

            await self._client.upsert(
                collection_name=self._collection,
                points=qdrant_points,
                wait=True,
            )

        except VectorCollectionError:
            raise
        except Exception as exc:
            raise VectorUpsertError(f"Failed to upsert vectors to Qdrant collection: {self._collection}") from exc

    def _build_prefetch(
        self,
        vector: list[float],
        text: str,
        *,
        score_threshold: float | None,
        limit: int,
    ) -> list[models.Prefetch]:
        """Build prefetch list for hybrid search.

        Dense prefetch uses cosine similarity; sparse uses BM25 via qdrant/bm25 model.
        score_threshold applies to dense candidates only (BM25 scale is not comparable).
        """
        return [
            models.Prefetch(
                query=vector,
                using="dense_vector",
                score_threshold=score_threshold,
                limit=limit,
            ),
            models.Prefetch(
                query=Document(text=text, model=self.bm25_model),
                using="bm25_sparse_vector",
                limit=limit,
            ),
        ]


    def _build_filter(self, doc_id: uuid.UUID | None) -> Filter | None:
        """Return a doc_id filter or None if no filtering is needed."""
        if doc_id is None:
            return None
        return Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))])


    async def search(
        self,
        query_vector: list[float],
        query_text: str,
        *,
        top_k: int = 5,
        doc_id: uuid.UUID | None = None,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """See VectorStorageProvider. Hybrid dense+BM25 search fused via self._fusion."""
        if not query_vector:
            return []

        prefetch = self._build_prefetch(
            vector=query_vector,
            text=query_text,
            score_threshold=None,
            limit=top_k * 2,
        )
        query_filter = self._build_filter(doc_id)

        try:
            results = await self._client.query_points(
                collection_name=self._collection,
                prefetch=prefetch,
                query=models.FusionQuery(fusion=self._fusion),
                limit=max(1, top_k),
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
        except Exception as exc:
            raise VectorSearchError(f"Failed to execute vector search in Qdrant {exc=}") from exc


    async def batch_search(
        self,
        query_vectors: list[list[float]],
        query_texts: list[str],
        *,
        top_k: int = 5,
        doc_id: uuid.UUID | None = None,
        score_threshold: float | None = None,
    ) -> list[list[dict]]:
        """See VectorStorageProvider. Each request uses hybrid prefetch fused via self._fusion."""
        if not query_vectors:
            return []

        query_filter = self._build_filter(doc_id)

        try:
            requests = [
                QueryRequest(
                    prefetch=self._build_prefetch(
                        vector=query_vector,
                        text=query_text,
                        score_threshold=None,
                        limit=top_k * 2,
                    ),
                    query=models.FusionQuery(fusion=self._fusion),
                    filter=query_filter,
                    limit=max(1, top_k),
                    score_threshold=score_threshold,
                    with_payload=True,
                )
                for query_vector, query_text in zip(query_vectors, query_texts, strict=True)
            ]
        except ValueError as exc:
            raise VectorSearchInputError(
                f"query_vectors and query_texts length mismatch: "
                f"{len(query_vectors)} != {len(query_texts)}"
            ) from exc

        try:
            batch_results = await self._client.query_batch_points(
                collection_name=self._collection,
                requests=requests,
            )

            return [
                [
                    {
                        "id": r.id,
                        "score": float(r.score),
                        "payload": r.payload or {},
                    }
                    for r in result.points
                ]
                for result in batch_results
            ]
        except Exception as exc:
            raise VectorSearchError(f"Failed to execute batch vector search in Qdrant {exc=}") from exc


    async def delete_points(self, doc_id: uuid.UUID) -> None:
        """Delete every vector point that belongs to one document.

        Document ownership is resolved by payload field `doc_id`.
        """
        try:
            await self._client.delete(
                collection_name=self._collection,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="doc_id",
                                match=MatchValue(value=str(doc_id)),
                            ),
                        ],
                    )
                ),
                wait=True,
            )
        except Exception as exc:
            raise VectorDeleteError(f"Failed to delete vectors for doc_id={doc_id}") from exc

    async def _ensure_collection(self, vector_size: int) -> None:
        async with self._collection_lock:
            """Create the target collection lazily if it does not exist yet.
    
            The collection schema is derived from the first upserted vector size
            and the configured distance/index optimizer settings.
            """
            try:
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
                    vectors_config={"dense_vector": VectorParams(size=vector_size, distance=self._distance)},
                    sparse_vectors_config={"bm25_sparse_vector": models.SparseVectorParams(modifier=models.Modifier.IDF)},
                    hnsw_config=hnsw_config,
                    optimizers_config=optimizers_config,
                    wal_config=wal_config,
                    )

            except Exception as exc:
                raise VectorCollectionError("Failed to ensure Qdrant collection") from exc

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
