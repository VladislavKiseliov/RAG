from __future__ import annotations

from rag_service.infrastructures.providers.embedding_provider import EmbeddingProvider


class VectorIndexingService:
    """
    Application-level service for text vectorization.

    Responsibilities:
        - Orchestrate batching logic for heavy embedding tasks.
        - Validate input strings before processing.
        - Provide a clean interface for single query and batch document vectorization.
    """

    def __init__(self, embedding_provider: EmbeddingProvider, batch_size: int = 64):
        """
        Initializes the service with a persistent embedding provider.

        Args:
            embedding_provider: A shared instance of the model provider.
            batch_size: Number of texts to process in a single model pass.
        """
        self._embedding_provider = embedding_provider
        self._batch_size = max(1, batch_size)

    async def get_query_embedding(self, query: str) -> list[float]:
        """
        Converts a single user query into an embedding vector.

        Args:
            query: User's natural language input.

        Returns:
            A list of floats representing the query in vector space.
        """
        clean_query = query.strip()
        if not clean_query:
            raise RuntimeError("Query text cannot be empty or whitespace only.")

        vectors = await self._embedding_provider.embed([clean_query])

        if not vectors:
            raise RuntimeError("Embedding provider failed to generate a vector.")

        return vectors[0]

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Converts a list of document chunks into embeddings using batching.

        Args:
            texts: List of strings to vectorize.

        Returns:
            A list of embedding vectors (lists of floats).
        """
        if not texts:
            return []

        # Optional: check for empty chunks to avoid model errors
        if any(not t.strip() for t in texts):
            raise ValueError("Input list contains empty or invalid strings.")

        all_vectors = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start: start + self._batch_size]
            batch_vectors = await self._embedding_provider.embed(batch)
            all_vectors.extend(batch_vectors)

        return all_vectors







