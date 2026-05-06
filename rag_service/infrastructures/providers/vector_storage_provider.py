from typing import Protocol, Any, runtime_checkable, List, Dict, Optional
import uuid


@runtime_checkable
class VectorStorageProvider(Protocol):
    """
    Protocol for vector storage operations.

    Defines a clean interface for persisting embeddings, performing
    geometric similarity searches, and managing document-scoped data.

    This interface is model-agnostic: it accepts pre-computed vectors
    rather than raw text strings.
    """

    async def upsert_vectors(
            self,
            doc_id: uuid.UUID,
            childs: List[Dict[str, Any]],
            vectors: List[List[float]]
    ) -> None:
        """
        Persists pre-computed vectors and their associated metadata.

        Args:
            doc_id: Unique identifier of the source document.
            childs: List of chunk data (metadata, text, etc.) from the application.
            vectors: List of corresponding embedding vectors.
        """
        ...

    async def search(
            self,
            query_vector: List[float],
            *,
            top_k: int = 5,
            doc_id: Optional[uuid.UUID] = None,
            score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs a similarity search using a pre-computed vector.

        Args:
            query_vector: A single embedding vector representing the search query.
            top_k: Maximum number of similar points to return.
            doc_id: Optional filter to restrict search to a specific document.
            score_threshold: Minimum similarity score threshold (0.0 to 1.0).

        Returns:
            List[Dict[str, Any]]: Search hits containing 'id', 'score', and 'payload'.
        """
        ...

    async def delete_points(self, doc_id: uuid.UUID) -> None:
        """
        Removes all vector points associated with a specific document.

        Args:
            doc_id: UUID of the document whose vectors should be deleted.
        """
        ...