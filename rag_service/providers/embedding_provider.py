  from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Абстракция для получения эмбеддингов по списку текстов."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...
