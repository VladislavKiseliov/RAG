from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, Protocol

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ConfigDict, Field


class QueryRouterProtocol(Protocol):
    def route(self, query: str) -> Literal["smalltalk", "domain_rag", "out_of_domain"]:
        ...

class RetrieveItemMetadata(BaseModel):
    """Document reference metadata: source document, page, and search score."""
    doc_id: str
    parent_id: str
    page_num: str | None = None
    score: float
    headers: dict[str, Any] = Field(default_factory=dict)
    source: str = ""


class ChildChunk(BaseModel):
    """A single child chunk from Qdrant — relevant text fragment with its similarity score."""
    text: str
    score: float


class RetrieveItem(BaseModel):
    """One RAG search result: matched child chunks, full parent text, and document metadata."""
    child_chunks: list[ChildChunk]
    parent_chunk: str
    metadata: RetrieveItemMetadata


class RetrievalResult(BaseModel):
    """Response from the RAG service for a retrieval request."""
    items: list[RetrieveItem]
    total: int


class FinalPromptData(BaseModel):
    """All data required to build the LLM prompt: context, chat history, summary, and current query."""
    route : str
    context: str
    chat_history: str
    summary: str
    current_query: str


class ExpandedQueryPack(BaseModel):
    """Original query together with its expanded reformulations to improve recall."""
    original_query: str
    queries: list[str] = Field(default_factory=list)


class LeanAgentState(BaseModel):
    """LangGraph pipeline state carried across all agent nodes."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Вводные данные
    query: str
    messages: list[dict[str, str]]
    summary: str = ""

    # Логика и маршрутизация
    route: Literal["smalltalk", "domain_rag", "out_of_domain"]
    expanded_queries: list[str] = Field(default_factory=list)

    # Контекст (Результат поиска)
    retrieval_data: list[RetrieveItem] = Field(default_factory=list)
    final_context: FinalPromptData | None = None

    response_model:str = ""
