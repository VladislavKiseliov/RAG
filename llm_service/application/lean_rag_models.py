from __future__ import annotations

import operator
from typing import Annotated, Any, Literal

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, ConfigDict, Field


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
    """All data required to build the LLM prompt: context, chat history, summary, and current query.

    chat_history - список сырых сообщений [{"role": "user"/"assistant", "content": ...}, ...]
    в хронологическом порядке (не отформатированная строка) - LLM_provider.py строит из
    них отдельные role-сообщения в запросе к LLM API, а не склеивает текстом в один блок
    (см. ISSUES.md/сессию про хронологию истории)."""
    route : str
    context: str
    chat_history: list[dict[str, str]]
    summary: str
    current_query: str


class ExpandedQueryPack(BaseModel):
    """Original query together with its expanded reformulations to improve recall."""
    original_query: str
    queries: list[str] = Field(default_factory=list)


class DocumentPassport(BaseModel):
    """Cheap per-document summary used by `plan` to decide comparison axes without
    re-reading full documents. See ARCHITECTURE.md §3 gather_passports."""
    doc_id: str
    filename: str
    summary: str = ""
    chapters: list[str] = Field(default_factory=list)
    is_fallback: bool = False


class PlanSubtask(BaseModel):
    """One tool invocation requested by `plan` — `tool` is any read-tool name
    registered in tool_registry.py, `args` validated against its args_schema
    at execute_subtasks-time."""
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class PlanOutput(BaseModel):
    """`plan` node's structured output. See ARCHITECTURE.md §3 contracts."""
    subtasks: list[PlanSubtask] = Field(default_factory=list)
    synthesis: str = ""


class ReflectOutput(BaseModel):
    """`reflect` node's structured verdict. See ARCHITECTURE.md §3 reflect."""
    verdict: Literal["sufficient", "need_more", "not_in_corpus"]
    new_queries: list[str] = Field(default_factory=list)
    needs_appendix: bool = False


class ProposedAction(BaseModel):
    """`post_actions` node's output — never auto-executed, requires human confirm
    via POST /actions/execute. See ARCHITECTURE.md §4 update_note rules."""
    action: Literal["create_task", "create_note", "update_note"]
    payload: dict[str, Any] = Field(default_factory=dict)


class LeanAgentState(BaseModel):
    """LangGraph pipeline state carried across all agent nodes."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Вводные данные
    query: str
    messages: list[dict[str, str]]
    summary: str = ""

    # Логика и маршрутизация
    route: Literal["smalltalk", "domain_rag", "out_of_domain", "personal", "complex"]
    expanded_queries: list[str] = Field(default_factory=list)

    # Контекст (Результат поиска)
    retrieval_data: list[RetrieveItem] = Field(default_factory=list)
    final_context: FinalPromptData | None = None

    # complex-путь (resolve_docs/gather_passports/plan/execute_subtasks) - см.
    # ARCHITECTURE.md §3. Заглушки в этом заходе, но поля нужны графу уже сейчас,
    # чтобы новые ноды и реальные могли писать в общий state.
    resolved_docs: list[str] = Field(default_factory=list)
    document_passports: list[DocumentPassport] = Field(default_factory=list)
    plan: PlanOutput | None = None
    subtask_results: list[dict[str, Any]] = Field(default_factory=list)

    reflect_rounds: int = 0
    reflect_verdict: Literal["sufficient", "need_more", "not_in_corpus"] | None = None
    retrieval_empty: bool = False

    sources: list[dict[str, Any]] = Field(default_factory=list)
    proposed_action: ProposedAction | None = None

    # A21 (rag_service/ISSUES.md): приложения не проходят через ChapterSplitter, значит
    # retrieval_data их никогда не содержит - reflect_node подтягивает текст напрямую
    # из rag_service (RetrievalService.get_appendix), в отдельное поле, а не в
    # retrieval_data, чтобы не потерять его при повторном execute_subtasks (need_more
    # затирает retrieval_data свежими результатами поиска, см. merge_search_docs_results).
    appendix_context: str = ""

    response_model:str = ""
    # True только когда generate_node дописал служебную ноту поверх/вместо реального
    # ответа (обрыв стрима, полный сбой LLM) - НЕ выставляется в no_data_node (тот
    # отдаёт честный, полноценный ответ "нет информации", не деградацию). Сигнал для
    # backend: не подмешивать такое сообщение в историю/саммари следующих ходов.
    response_degraded: bool = False
