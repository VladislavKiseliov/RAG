# rag_service/infrastructures/services/sparse_embedding_service.py
import asyncio
from typing import List
from fastembed import SparseTextEmbedding
from rag_service.domain.models.vector_point import SparseVectorValue


class BM25EmbeddingService:
    """Сервис для локальной генерации разреженных векторов (BM25).
    Использует быстрый движок fastembed от Qdrant.
    """

    def __init__(self, model_name: str = "Qdrant/bm25") -> None:
        # Инициализируем модель. Она скачивается один раз при первом запуске
        # и работает очень быстро на CPU, поэтому ее можно держать в Stateless
        self._model = SparseTextEmbedding(model_name=model_name)

    async def get_sparse_embeddings(self, texts: List[str]) -> List[SparseVectorValue]:
        """Превращает список текстов в список доменных спарс-векторов."""
        if not texts:
            return []

        # Напрямую генерируем вектора.
        # Метод возвращает генератор объектов, у которых есть .indices и .values
        embeddings_generator = await asyncio.to_thread(self._model.embed, texts)

        result = []
        for emb in embeddings_generator:
            result.append(
                SparseVectorValue(
                    indices=list(emb.indices),
                    values=list(emb.values)
                )
            )
        return result