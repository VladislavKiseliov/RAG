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

from rag_service.domain.errors.vector import (
    VectorCollectionError,
    VectorDeleteError,
    VectorSearchError,
    VectorUpsertError,
)
from rag_service.infrastructures.providers.embedding_provider import EmbeddingProvider


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
        self._distance = Distance[distance.upper()]
        self._upsert_batch_size = max(1, upsert_batch_size)
        self._hnsw_m = hnsw_m
        self._hnsw_ef_construct = hnsw_ef_construct
        self._optimizers_default_segment_number = optimizers_default_segment_number
        self._optimizers_memmap_threshold = optimizers_memmap_threshold
        self._optimizers_indexing_threshold = optimizers_indexing_threshold
        self._wal_capacity_mb = wal_capacity_mb

    async def upsert_vectors(self, doc_id: uuid.UUID, childs: list,vectors:list[list[float]]) -> None:
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

        points = self._creates_points(doc_id, childs, vectors)

        if not points:
            return

        first_vector = points[0].get("vector")
        if not first_vector:
            raise RuntimeError("Point vector is empty")

        try:
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
        except VectorCollectionError:
            raise
        except Exception as exc:
            raise VectorUpsertError("Failed to upsert vectors to Qdrant") from exc

    def _creates_points(self,doc_id: uuid.UUID, childs: list,vectors:list[list[float]]) -> list[dict]:
        """
                Internal mapper that assembles the dictionary structure for Qdrant points.

                This method ensures that the 'text' and 'doc_id' are always present
                in the point's payload for efficient retrieval and filtering.
                """
        if not childs or not vectors:
            return []

        ready_points = []
        for child, vector in zip(childs, vectors, strict=True):
            ready_points.append(
                {
                    "id": child.get("id") or str(uuid.uuid4()),
                    "vector": vector,
                    "payload": {
                        "parent_id": child["parent_id"],
                        "headers": child.get("headers") or {},
                        "text": child["text"],
                        "source": child.get("source", ""),
                        "doc_id": str(doc_id),
                    },
                }
            )

        return ready_points


    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        doc_id: uuid.UUID | None = None,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """
        Executes a vector similarity search in the Qdrant collection.

        This method is "model-agnostic," meaning it only handles pre-computed
        embeddings. It performs a geometric search to find the nearest
        neighbors in the vector space.

        Args:
            query_vector: A single embedding vector representing the search query.
            top_k: The maximum number of similar points to return. Defaults to 5.
            doc_id: Optional UUID to restrict the search to a specific document's chunks.
            score_threshold: Optional minimum similarity score (0.0 to 1.0)
                to filter out irrelevant results.

        Returns:
            List[Dict[str, Any]]: A list of search hits, where each hit contains
                the point 'id', similarity 'score', and the associated 'payload'.
                Returns an empty list if no results are found or if the query_vector is empty.
        """

        if not query_vector:
            return []

        query_filter = None
        if doc_id is not None:
            query_filter = Filter(
                must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))]
            )
        print(f"Querying Qdrant with {query_vector=}")
        try:

            results = await self._client.query_points(
                collection_name=self._collection,
                query=query_vector,
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
        except Exception as exc:
            print(f"{exc=}")
            raise VectorSearchError(f"Failed to execute vector search in Qdrant {exc=}") from exc

    async def delete(self, doc_id: uuid.UUID) -> None:
        """Delete every vector point that belongs to one document.

        Document ownership is resolved by payload field `doc_id`.
        """
        try:
            await self._client.delete(
                collection_name=self._collection,
                points_selector=Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=str(doc_id)))]
                ),
                wait=True,
            )
        except Exception as exc:
            raise VectorDeleteError(f"Failed to delete vectors for doc_id={doc_id}") from exc

    async def _ensure_collection(self, vector_size: int) -> None:
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
                vectors_config=VectorParams(size=vector_size, distance=self._distance),
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
