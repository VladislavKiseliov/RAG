from dataclasses import dataclass, field
import uuid
from typing import Any, List


@dataclass(frozen=True)
class SparseVectorValue:
    """Чистая доменная структура разреженного вектора."""
    indices: List[int]
    values: List[float]


@dataclass(frozen=True)
class VectorPoint:
    """Чистая доменная модель точки для векторного хранилища.
    Полностью изолирована от конкретных драйверов (Qdrant/PgVector).
    """
    id: str | uuid.UUID
    dense_vector: list[float]
    sparse_vector: SparseVectorValue
    text: str
    payload: dict[str, Any] = field(default_factory=dict)

