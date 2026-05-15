from __future__ import annotations

from typing import Any, List, Dict

from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    history_massage: List[Dict]
    summary: str
    doc_id: str | None = None
    include_context: bool = False

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query cannot be empty")
        return value


class SourceItem(BaseModel):
    doc_id: str
    parent_id: str
    page_num: str | None = None
    score: float
    text: str
    headers: dict[str, Any] = Field(default_factory=dict)


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    context: str | None = None
    total: int

