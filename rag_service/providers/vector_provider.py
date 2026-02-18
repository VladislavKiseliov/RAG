from __future__ import annotations

import uuid
from typing import Protocol


class VectorProvider(Protocol):
    """Абстракция для записи векторных представлений.

    Реализация может отправлять данные в Qdrant или другой стор.
    """

    async def upsert(self, doc_id: uuid.UUID, chunks: list[str], meta: dict | None) -> None:
        ...

    async def delete(self, doc_id: uuid.UUID) -> None:
        ...


class NullVectorProvider:
    """Заглушка векторного хранилища.

    Используется, когда векторная БД не подключена.
    """

    async def upsert(self, doc_id: uuid.UUID, chunks: list[str], meta: dict | None) -> None:
        return None

    async def delete(self, doc_id: uuid.UUID) -> None:
        return None
