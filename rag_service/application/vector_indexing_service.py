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
        - Apply the e5 instruction prefix ("query: " / "passage: ") the embedding model
          was trained with — the provider only sees raw text, so the prefix has to be
          added here, where the caller's intent (query vs. passage) is actually known.
    """

    _QUERY_PREFIX = "query: "
    _PASSAGE_PREFIX = "passage: "

    def __init__(self,
                 embedding_provider: EmbeddingProvider,
                 sparse_provider:BM25EmbeddingService
                 ):
        """
        Initializes the service with a persistent embedding provider.

        Args:
            embedding_provider: A shared instance of the models provider.
        """
        self._embedding_provider = embedding_provider
        self._sparse_provider= sparse_provider # Наш BM25 (FastEmbed)

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Эмбеддинг поисковых запросов — префикс "query: " (обязателен для e5-семейства).

        Использовать только для текста, которым ищут. Никогда не звать для контента
        документов/заметок — перепутанный префикс тихо портит качество retrieval,
        без единой ошибки в рантайме.
        """
        if not texts:
            return []
        prefixed = [f"{self._QUERY_PREFIX}{t}" for t in texts]
        return await self._embedding_provider.embed(prefixed)

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Эмбеддинг контента для индексации — префикс "passage: " (обязателен для e5-семейства).

        Использовать только для текста документов/заметок, который попадёт в индекс.
        Никогда не звать для запросов — см. предупреждение в embed_queries().
        """
        if not texts:
            return []
        prefixed = [f"{self._PASSAGE_PREFIX}{t}" for t in texts]
        return await self._embedding_provider.embed(prefixed)

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

        vectors = await self.embed_queries([clean_query])

        if not vectors:
            raise RuntimeError("Embedding provider failed to generate a vector.")

        return vectors[0]

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Converts a batch of search queries into embeddings (query-side only — see
        embed_queries()). Despite the generic name, this is not for document/note
        content; that path is get_dense_vectors()/get_hybrid_vectors().

        Args:
            texts: List of strings to vectorize.

        Returns:
            A list of embedding vectors (lists of floats).
        """
        if not texts:
            return []

        # Optional: check for empty chunks to avoid models errors
        if any(not t.strip() for t in texts):
            raise ValueError("Input list contains empty or invalid strings.")


        vectors = await self.embed_queries(texts)

        return vectors


    async def get_dense_vectors(self, texts: List[str]) -> List[List[float]]:
        """Плотные вектора для контента, который индексируется (passage-side only —
        см. embed_passages()). Не использовать для запросов."""
        if not texts:
            return []

        return await self.embed_passages(texts)

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







