from __future__ import annotations

import asyncio

from rag_service.domain.models.vector_point import SparseVectorValue
from rag_service.infrastructures.providers.embedding_provider import EmbeddingProvider
from typing import List, Tuple

from rag_service.infrastructures.repositories.bm25_embedding_service import BM25EmbeddingService


class VectorIndexingService:
    """
    Application-level service for text vectorization.

    Responsibilities:
        - Orchestrate batching logic for heavy embedding tasks.
        - Validate input strings before processing.
        - Provide a clean interface for single query and batch document vectorization.
    """

    def __init__(self,
                 embedding_provider: EmbeddingProvider,
                 sparse_provider:BM25EmbeddingService
                 ):
        """
        Initializes the service with a persistent embedding provider.

        Args:
            embedding_provider: A shared instance of the model provider.
        """
        self._embedding_provider = embedding_provider
        self._sparse_provider= sparse_provider # Наш BM25 (FastEmbed)


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


        vectors = await self._embedding_provider.embed(texts)

        return vectors


    async def get_dense_vectors(self, texts: List[str]) -> List[List[float]]:
        """Получить только плотные вектора (например, для специфичных задач)"""
        if not texts:
            return []

        return await self._embedding_provider.embed(texts)

    async def get_sparse_vectors(self, texts: List[str]) -> List[SparseVectorValue]:
        if not texts:
            return []

        """Получить только разреженные вектора"""
        return await self._sparse_provider.get_sparse_embeddings(texts)


    async def get_hybrid_vectors(self, texts: List[str]) -> Tuple[List[List[float]], List[SparseVectorValue]]:
        """Получить оба вектора одновременно для гибридного RAG.
        Вычисления запускаются параллельно для максимальной скорости!
        """
        import asyncio

        # Запускаем генерацию плотных и разреженных векторов одновременно,
        # чтобы процессор/видеокарта работали параллельно и не ждали друг друга
        dense_task = self.get_dense_vectors(texts)
        sparse_task =  self.get_sparse_vectors(texts)

        dense_vectors, sparse_vectors = await asyncio.gather(dense_task, sparse_task)

        return dense_vectors, sparse_vectors







