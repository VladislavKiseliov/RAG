"""Application-уровня модели результатов - не транспортный контракт (api/schemas.py).

Роутер (api/rag_routes.py) объявляет response_model=<api-схема> на эндпоинте и мапит
эти значения на HTTP-контракт на границе - application-слой ничего не знает о FastAPI/
Pydantic-схемах транспорта, что позволяет вызывать его не только из HTTP (Celery-задачи,
CLI, будущий аудит-конвейер)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict


class RetrieveItemMetadataDict(TypedDict):
    doc_id: str
    parent_id: str
    page_num: str | None
    score: float
    headers: dict[str, Any]
    source: str


class ChildChunkDict(TypedDict):
    text: str
    score: float


class RetrieveItemDict(TypedDict):
    child_chunks: list[ChildChunkDict]
    parent_chunk: str
    metadata: RetrieveItemMetadataDict


class RetrieveResultDict(TypedDict):
    items: list[RetrieveItemDict]
    total: int


@dataclass(frozen=True)
class UploadLinkResult:
    doc_id: str
    presigned_url: str
