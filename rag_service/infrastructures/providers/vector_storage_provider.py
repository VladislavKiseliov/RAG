from typing import Protocol, Any, runtime_checkable
import uuid


@runtime_checkable
class VectorStorageProvider(Protocol):
    """
    Протокол для векторного хранилища.

    Определяет методы для сохранения векторов, семантического поиска
    и управления данными на уровне документов.
    """

    async def upsert_vectors(self, points: list[dict[str, Any]]) -> None:
        """
        Сохраняет уже подготовленные векторы и метаданные (payload) в хранилище.

        Args:
            points: Список словарей. Каждый словарь должен содержать:
                - "id": уникальный идентификатор (int/UUID/str)
                - "vector": список float (эмбеддинг)
                - "payload": метаданные чанка (текст, doc_id и т.д.)
        """
        ...

    async def search(
            self,
            query: str,
            *,
            top_k: int = 5,
            doc_id: uuid.UUID | None = None,
            score_threshold: float | None = None
    ) -> list[dict[str, Any]]:
        """
        Выполняет семантический поиск по текстовому запросу.

        Внутри метода происходит векторизация запроса и поиск ближайших соседей.

        Args:
            query: Текст поискового запроса.
            top_k: Количество возвращаемых результатов.
            doc_id: Опциональный фильтр для поиска только внутри одного документа.
            score_threshold: Минимальный порог сходства (0.0 - 1.0).

        Returns:
            list[dict]: Список найденных чанков с их score и payload.
        """
        ...

    async def delete(self, doc_id: uuid.UUID) -> None:
        """
        Удаляет все векторные точки, связанные с конкретным документом.

        Args:
            doc_id: UUID документа, чьи векторы нужно удалить.
        """
        ...