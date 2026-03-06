from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable


@runtime_checkable
class VectorProvider(Protocol):
    """Интерфейс для работы с векторным хранилищем."""

    async def upsert_with_payload(self, doc_id: uuid.UUID, points: list[dict]) -> None:
        """Генерирует эмбеддинги и записывает точки с произвольным payload.

        Args:
            doc_id: Идентификатор документа.
            points: Список точек. Каждая точка содержит:
                - text: текст для эмбеддинга
                - payload: словарь метаданных (опционально)
                - id: идентификатор точки (опционально)
        """
        ...

    async def upsert(self, doc_id: uuid.UUID, chunks: list[str], meta: dict | None) -> None:
        """Записывает список текстовых чанков с минимальным payload.

        Args:
            doc_id: Идентификатор документа.
            chunks: Список текстовых чанков для векторизации.
            meta: Опциональные метаданные добавляемые к каждой точке.
        """
        ...

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        doc_id: uuid.UUID | None = None,
        score_threshold: float | None = None,
    ) -> list[dict]:
        """Поиск ближайших чанков по текстовому запросу.

        Args:
            query: Текстовый запрос пользователя.
            top_k: Максимальное количество результатов.
            doc_id: Опциональный фильтр по документу.
            score_threshold: Минимальный порог релевантности.

        Returns:
            Список hits: [{"id": ..., "score": float, "payload": dict}]
        """
        ...

    async def delete(self, doc_id: uuid.UUID) -> None:
        """Удаляет все точки документа из хранилища.

        Args:
            doc_id: Идентификатор документа для удаления.
        """
        ...