from typing import Protocol, Any, runtime_checkable, List, Dict, Optional
import uuid

from rag_service.domain.models.vector_point import VectorPoint


@runtime_checkable
class VectorStorageProvider(Protocol):
    """Contract for hybrid vector storage operations.

    Accepts pre-computed dense vectors and raw query text for sparse search.
    Implementations are responsible for fusing dense and sparse results.
    """

    async def upsert_vectors(self, points: List[VectorPoint]) -> None:
        """Persist a batch of domain vector points.

        Args:
            points: Pre-computed domain points (dense + sparse vectors + payload).
        """
        ...

    async def search(
            self,
            query_vector: List[float],
            query_text: str,
            *,
            top_k: int = 5,
            doc_id: Optional[uuid.UUID] = None,
            score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Hybrid similarity search for a single query.

        Args:
            query_vector: Pre-computed dense embedding of the query.
            query_text: Raw query text used for sparse (BM25) search.
            top_k: Maximum number of results to return.
            doc_id: Optional filter to restrict search to one document.
            score_threshold: Minimum score threshold applied to dense candidates.

        Returns:
            List of hits ordered by relevance. Each hit: {id, score, payload}.
        """
        ...

    async def batch_search(
            self,
            query_vectors: List[List[float]],
            query_texts: List[str],
            *,
            top_k: int = 5,
            doc_id: Optional[uuid.UUID] = None,
            score_threshold: Optional[float] = None,
    ) -> List[List[Dict[str, Any]]]:
        """Hybrid search for multiple queries in a single round-trip.

        Args:
            query_vectors: Dense embeddings, one per query.
            query_texts: Raw query texts for sparse search. Must match query_vectors length.
            top_k: Maximum hits per query.
            doc_id: Optional filter to restrict search to one document.
            score_threshold: Minimum score threshold applied to dense candidates.

        Returns:
            List of hit lists, one per input query, in the same order.

        Raises:
            VectorSearchInputError: If query_vectors and query_texts have different lengths.
        """
        ...

    async def delete_by_field(self, field: str, value: str) -> None:
        """Remove all vector points whose payload[field] == value.

        Args:
            field: Payload field name to match on (e.g. "doc_id", "note_id").
            value: Value to match.
        """
        ...