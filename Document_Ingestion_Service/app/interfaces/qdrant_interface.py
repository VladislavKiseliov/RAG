from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from langchain.schema import Document


class QdrantInterface(ABC):
    """Base interface for Qdrant operations (ingest + retrieval)."""

    @abstractmethod
    def upsert(self, vectors: List[List[float]], payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert vectors and payloads into Qdrant."""
        pass

    @abstractmethod
    def get_retriever(self, search_kwargs: Optional[Dict[str, Any]] = None) -> Any:
        """Return a retriever for searching."""
        pass

    @abstractmethod
    def similarity_search(self, query: str, k: int = 5, **kwargs) -> List[Document]:
        """Semantic search over the collection."""
        pass
