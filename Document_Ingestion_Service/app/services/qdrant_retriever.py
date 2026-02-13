from typing import Any, Dict, Optional

from langchain_community.vectorstores import Qdrant as LangChainQdrant

from ..config import MAX_RESULTS, SIMILARITY_THRESHOLD


class QdrantRetriever:
    def __init__(
        self,
        embeddings: Any,
        collection_name: str,
        qdrant_url: str,
        search_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
    ) -> None:
        self.embeddings = embeddings
        self.collection_name = collection_name
        self.qdrant_url = qdrant_url
        self.search_k = search_k if search_k is not None else MAX_RESULTS
        self.score_threshold = (
            score_threshold if score_threshold is not None else SIMILARITY_THRESHOLD
        )

    def _load_collection(self) -> LangChainQdrant:
        if not self.qdrant_url:
            raise ValueError("QDRANT_URL is not set")
        return LangChainQdrant.from_existing_collection(
            embedding=self.embeddings,
            collection_name=self.collection_name,
            url=self.qdrant_url,
        )

    def get_retriever(self, search_kwargs: Optional[Dict[str, Any]] = None) -> Any:
        if self.embeddings is None:
            raise ValueError("Embeddings are not initialized")

        if search_kwargs is None:
            search_kwargs = {
                "k": self.search_k,
                "score_threshold": self.score_threshold,
            }

        qdrant_db = self._load_collection()
        return qdrant_db.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs=search_kwargs,
        )
