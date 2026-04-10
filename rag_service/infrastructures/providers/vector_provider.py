from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable


@runtime_checkable
class VectorProvider(Protocol):
    """Interface for vector storage operations."""

    async def upsert_vectors(self, points: list[dict]) -> None:
        """Persist already-vectorized points into the vector store."""
        ...

    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        doc_id: uuid.UUID | None = None,
        score_threshold: float | None = None,
    ) -> list[dict]:
        ...

    async def delete(self, doc_id: uuid.UUID) -> None:
        ...
