from __future__ import annotations

from typing import Any, List, Dict

from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    history_messages: List[Dict]
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
    child_chunks: list[str] = Field(default_factory=list)
    headers: dict[str, Any] = Field(default_factory=dict)
    source: str = ""


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    context: str | None = None
    total: int


class SummaryRequest(BaseModel):
    messages: List[Dict]
    existing_summary: str = ""


class SummaryResponse(BaseModel):
    summary: str


class NoteGenerateRequest(BaseModel):
    raw_text: str = Field(..., min_length=1)

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("raw_text cannot be empty")
        return value


class NoteGenerateResponse(BaseModel):
    title: str
    content: str
    reminder: str | None = None
    tags: list[str] = Field(default_factory=list)
    folder: str | None = None


class ChapterSummaryRequest(BaseModel):
    chapter_text: str = Field(..., min_length=1)


class ChapterSummaryResponse(BaseModel):
    summary: str


class DocumentSummaryRequest(BaseModel):
    chapter_summaries: str = Field(..., min_length=1)


class DocumentSummaryResponse(BaseModel):
    summary: str

