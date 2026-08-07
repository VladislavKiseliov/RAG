from __future__ import annotations

from typing import Any, List, Dict

from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    history_messages: List[Dict]
    summary: str

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
    # Аддитивные поля (route/retrieval_empty с 2026-08-05, degraded с 2026-08-06 реально
    # заполняются живыми нодами - plan_node/no_data_node/generate_node; proposed_action
    # пока всегда None, post_actions_node - настоящая заглушка).
    # backend/services/ai/llm_client.py читает ответ через data.get(...), новые поля не
    # ломают существующий разбор.
    route: str | None = None
    retrieval_empty: bool = False
    proposed_action: dict[str, Any] | None = None
    # True, если generate_node дописал служебную ноту об обрыве/сбое поверх или вместо
    # ответа (не выставляется для честного no_data-ответа - тот полноценный). Backend
    # использует это, чтобы не подмешивать такие сообщения в историю/саммари следующих
    # ходов (см. conversation_service.py).
    degraded: bool = False


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


class TableSummaryRequest(BaseModel):
    table_text: str = Field(..., min_length=1)


class TableSummaryResponse(BaseModel):
    summary: str

