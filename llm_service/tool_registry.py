from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel

from llm_service.application.services.retrieval_service import RetrievalService

# Framework-agnostic — без импортов LangGraph, чтобы этим же реестром впоследствии
# мог пользоваться mcp_server.py (см. ARCHITECTURE.md §5). Реально работают три
# инструмента - search_docs, get_appendix, list_documents (все оборачивают
# RetrievalService). list_documents НЕ упомянут в plan_prompt (ai_config.toml) -
# planner о нём не знает и сам его не предложит; тул зарегистрирован и вызываем
# (в т.ч. для будущего использования вне графа), но живым LLM-трафиком сегодня
# не достигается. Всё остальное - настоящая заглушка: вызов fn кидает
# NotImplementedError, а не молча возвращает пустой "успех" - см. ARCHITECTURE.md §4/§10.


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_schema: type[BaseModel]
    fn: Callable[..., Awaitable[Any]]
    access: Literal["read", "write"]
    output_limit_tokens: int = 4000


class SearchDocsArgs(BaseModel):
    query: str
    doc_filter: str | None = None


class GetChapterArgs(BaseModel):
    doc: str
    chapter_number: str


class GetAppendixArgs(BaseModel):
    document_code: str


class GetDocumentPassportArgs(BaseModel):
    doc: str


class ListDocumentsArgs(BaseModel):
    pass


class SearchNotesArgs(BaseModel):
    query: str


class SearchTasksArgs(BaseModel):
    query: str


class CreateTaskArgs(BaseModel):
    title: str
    body: str


class CreateNoteArgs(BaseModel):
    title: str
    content: str


class UpdateNoteArgs(BaseModel):
    note_id: str
    patch: dict[str, Any]


class CalcGasArgs(BaseModel):
    params: dict[str, Any]


class RunAuditArgs(BaseModel):
    file_id: str


def _not_implemented_tool(name: str) -> Callable[..., Awaitable[Any]]:
    async def _fn(**_kwargs: Any) -> Any:
        raise NotImplementedError(
            f"Tool '{name}' is scaffolding only — see ARCHITECTURE.md §4/§10 for rollout plan"
        )

    return _fn


def build_tool_registry(*, retrieval_service: RetrievalService) -> dict[str, Tool]:
    """Строит реестр инструментов один раз при инициализации агента (см. LeanRagAgent.__init__).

    search_docs оборачивает RetrievalService.retrieve. doc_filter принимается схемой
    (для совместимости с будущим payload-фильтром document_code, см. ARCHITECTURE.md
    §10 8.1), но пока не применяется - retrieve() ещё не поддерживает фильтрацию по
    документу на стороне rag_service.
    """

    async def _search_docs(*, query: str, doc_filter: str | None = None) -> dict[str, Any]:
        result = await retrieval_service.retrieve([query])
        return {"items": [item.model_dump() for item in result.items], "total": result.total}

    async def _get_appendix(*, document_code: str) -> dict[str, Any]:
        doc_id = await retrieval_service.find_document_id_by_code(document_code)
        if doc_id is None:
            return {"text": None, "doc_id": None}
        text = await retrieval_service.get_appendix(doc_id)
        return {"text": text, "doc_id": doc_id}

    async def _list_documents() -> dict[str, Any]:
        documents = await retrieval_service.list_documents()
        return {"documents": documents, "total": len(documents)}

    return {
        "search_docs": Tool(
            name="search_docs",
            description="Гибридный поиск по базе знаний (Qdrant dense+BM25).",
            args_schema=SearchDocsArgs,
            fn=_search_docs,
            access="read",
        ),
        "get_appendix": Tool(
            name="get_appendix",
            description=(
                "Текст приложений (ПРИЛОЖЕНИЕ N) конкретного документа по его названию/номеру "
                "(например 'СП 1.13130.2020'). Приложения НЕ ищутся search_docs (не проиндексированы) - "
                "используй этот тул, когда пользователь явно называет документ и просит именно приложение."
            ),
            args_schema=GetAppendixArgs,
            fn=_get_appendix,
            access="read",
        ),
        "get_chapter": Tool(
            name="get_chapter",
            description="Текст главы документа из S3 (читалка).",
            args_schema=GetChapterArgs,
            fn=_not_implemented_tool("get_chapter"),
            access="read",
        ),
        "get_document_passport": Tool(
            name="get_document_passport",
            description="Готовое саммари документа для gather_passports.",
            args_schema=GetDocumentPassportArgs,
            fn=_not_implemented_tool("get_document_passport"),
            access="read",
        ),
        "list_documents": Tool(
            name="list_documents",
            description="Обзор корпуса — список документов базы знаний.",
            args_schema=ListDocumentsArgs,
            fn=_list_documents,
            access="read",
        ),
        "search_notes": Tool(
            name="search_notes",
            description="Postgres FTS по заметкам пользователя.",
            args_schema=SearchNotesArgs,
            fn=_not_implemented_tool("search_notes"),
            access="read",
        ),
        "search_tasks": Tool(
            name="search_tasks",
            description="Postgres FTS по задачам пользователя.",
            args_schema=SearchTasksArgs,
            fn=_not_implemented_tool("search_tasks"),
            access="read",
        ),
        "create_task": Tool(
            name="create_task",
            description="Создать задачу — только через proposed_action + подтверждение.",
            args_schema=CreateTaskArgs,
            fn=_not_implemented_tool("create_task"),
            access="write",
        ),
        "create_note": Tool(
            name="create_note",
            description="Создать заметку — только через proposed_action + подтверждение.",
            args_schema=CreateNoteArgs,
            fn=_not_implemented_tool("create_note"),
            access="write",
        ),
        "update_note": Tool(
            name="update_note",
            description="Поправить существующую заметку — diff-чип + optimistic lock по note_updated_at.",
            args_schema=UpdateNoteArgs,
            fn=_not_implemented_tool("update_note"),
            access="write",
        ),
        "calc_gas": Tool(
            name="calc_gas",
            description="Детерминированные газовые расчёты (не LLM).",
            args_schema=CalcGasArgs,
            fn=_not_implemented_tool("calc_gas"),
            access="read",
        ),
        "run_audit": Tool(
            name="run_audit",
            description="Постановка Celery agent-run для аудита опросного листа.",
            args_schema=RunAuditArgs,
            fn=_not_implemented_tool("run_audit"),
            access="write",
        ),
    }
