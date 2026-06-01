from typing import Protocol, Any, runtime_checkable, List, Dict, Optional
import uuid


@runtime_checkable
class VectorStorageProvider(Protocol):
    """Contract for hybrid vector storage operations.

    Accepts pre-computed dense vectors and raw query text for sparse search.
    Implementations are responsible for fusing dense and sparse results.
    """

    async def upsert_vectors(
            self,
            doc_id: uuid.UUID,
            childs: List[Dict[str, Any]],
            vectors: List[List[float]]
    ) -> None:
        """Persist pre-computed dense vectors with associated chunk metadata.

        Args:
            doc_id: Source document identifier.
            childs: Chunk dicts with keys: id, text, parent_id, headers, source.
            vectors: Dense embedding vectors aligned with childs (same order and length).
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

    async def delete_points(self, doc_id: uuid.UUID) -> None:
        """Remove all vector points belonging to a document.

        Args:
            doc_id: Document whose points should be deleted.
        """
        ...