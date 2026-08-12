from __future__ import annotations

import json
from collections.abc import AsyncIterable

from typing import Awaitable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from openai import APIStatusError, RateLimitError

from llm_service.exceptions import LLMQuotaExceededError, LLMRateLimitedError, LLMServiceError
from llm_service.utils.cancellation import with_cancellation
from llm_service.api.schemas import (
    AskRequest,
    AskResponse,
    ChapterSummaryRequest,
    ChapterSummaryResponse,
    DocumentSummaryRequest,
    DocumentSummaryResponse,
    NoteGenerateRequest,
    NoteGenerateResponse,
    SummaryRequest,
    SummaryResponse,
    TableSummaryRequest,
    TableSummaryResponse,
)
from llm_service.application.lean_rag_agent import LeanRagAgent
from llm_service.dependencies import get_lean_rag_agent
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.api")

router = APIRouter(prefix="/llm", tags=["llm"])

_T = TypeVar("_T")


async def _call_llm_provider(coro: Awaitable[_T], *, log_label: str) -> _T:
    """Общая обёртка над non-streaming вызовами llm_provider.generate_*: провайдерские
    rate-limit/quota-ошибки превращаются в типизированные LLMServiceError (обрабатываются
    глобальным llm_error_handler в main.py, отдают клиенту правильный код вместо
    одинакового 502 на всё подряд - тот скрывал реальную причину сбоя (429/402)."""
    try:
        return await coro
    except RateLimitError as exc:
        logger.exception("%s: provider rate-limited", log_label)
        raise LLMRateLimitedError() from exc
    except APIStatusError as exc:
        if exc.status_code == 402:
            logger.exception("%s: provider balance/quota exhausted", log_label)
            raise LLMQuotaExceededError() from exc
        logger.exception("%s failed", log_label)
        raise LLMServiceError(f"{log_label} failed", status_code=502) from exc
    except Exception as exc:
        logger.exception("%s failed", log_label)
        raise LLMServiceError(f"{log_label} failed", status_code=502) from exc


@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.post("/answer", response_model=AskResponse)
@with_cancellation
async def answer_question(
    request: AskRequest,
    http_request: Request,
    agent: LeanRagAgent = Depends(get_lean_rag_agent),
) -> AskResponse:
    try:
        logger.info("LLM request", extra={"query": json.dumps(request.query)})
        final_state = await agent.run(
            query=request.query,
            history_messages_db=request.history_messages,
            summary=request.summary,

        )
    except LLMServiceError:
        # RagUnavailableError/RagResponseError/RerankerUnavailableError/RerankerResponseError
        # (retrieval_service.py/reranker_service.py) несут собственный status_code (502/503) -
        # раньше терялись в except Exception ниже, все сбои становились одинаковым 502
        # "LLM pipeline failed", хотя main.py::llm_error_handler для этого и существует.
        # Пробрасываем дальше нетронутыми - FastAPI найдёт зарегистрированный хендлер.
        raise
    except Exception:
        # CancelledError (BaseException, не Exception) сюда не попадёт - при дисконнекте
        # клиента (см. with_cancellation) отвечать всё равно уже некому.
        logger.exception("LLM pipeline failed")
        raise HTTPException(status_code=502, detail="LLM pipeline failed")

    answer_text = final_state["response_model"]
    retrieval_data = final_state.get("retrieval_data", [])
    sources = LeanRagAgent.build_sources(retrieval_data)

    proposed_action = final_state.get("proposed_action")

    result = {
        "answer": answer_text,
        "sources": sources,
        "context": None,
        "total": len(sources),
        "route": final_state.get("route"),
        "retrieval_empty": final_state.get("retrieval_empty", False),
        "proposed_action": proposed_action.model_dump() if proposed_action else None,
        "degraded": final_state.get("response_degraded", False),
    }

    return AskResponse(**result)


@router.post("/answer/stream", response_class=EventSourceResponse)
async def answer_question_stream(
    request: AskRequest,
    agent: LeanRagAgent = Depends(get_lean_rag_agent),
) -> AsyncIterable[ServerSentEvent]:
    """SSE-вариант /answer: status -> token* -> sources -> done.

    HTTP-заголовки уходят до первого события, поэтому ошибка на любом этапе (в т.ч.
    после части токенов) не может стать HTTPException - вместо этого событие 'error',
    backend/фронт обрабатывают его сами (см. conversation_service.py/useAiChat.js).

    Keep-alive между событиями - забота EventSourceResponse (родной механизм FastAPI,
    см. fastapi/routing.py: producer/keepalive-inserter таски поверх anyio.fail_after,
    не отменяет то, что ждём, на таймауте) - run_stream() больше сам ничего не пингует.
    """
    logger.info("LLM stream request", extra={"query": json.dumps(request.query)})

    try:
        async for event in agent.run_stream(
            query=request.query,
            history_messages_db=request.history_messages,
            summary=request.summary,
        ):
            yield ServerSentEvent(event=event["event"], data=event["data"])
    except Exception:
        logger.exception("LLM stream pipeline failed")
        yield ServerSentEvent(event="error", data={"message": "LLM stream pipeline failed"})


@router.post("/summary", response_model=SummaryResponse)
async def summarize_messages(
    request: SummaryRequest,
    agent: LeanRagAgent = Depends(get_lean_rag_agent),
) -> SummaryResponse:
    summary = await _call_llm_provider(
        agent.llm_provider.generate_summary(
            messages=request.messages,
            existing_summary=request.existing_summary,
        ),
        log_label="Summary generation",
    )
    return SummaryResponse(summary=summary)


# Временный эндпоинт: генерация заметки из потока мыслей. Проксируется через
# backend/services/ai/llm_client.py (по образцу /llm/answer, /llm/summary) — напрямую с фронта
# не вызывается, это внутренний вызов backend -> llm_service.
# Набор тегов/папок зафиксирован под TAG_PALETTE/FOLDERS во frontend/src/hooks/useNotes.js —
# если палитра на фронте поменяется, поправить и здесь, и промпт в ai_config.toml.
ALLOWED_NOTE_TAGS = {"important", "idea", "todo", "question", "ref"}
ALLOWED_NOTE_FOLDERS = {"work", "ideas", "personal"}


@router.post("/note", response_model=NoteGenerateResponse)
async def generate_note(
    request: NoteGenerateRequest,
    agent: LeanRagAgent = Depends(get_lean_rag_agent),
) -> NoteGenerateResponse:
    raw = await _call_llm_provider(
        agent.llm_provider.generate_note(raw_text=request.raw_text), log_label="Note generation",
    )

    try:
        parsed = json.loads(raw)
        title = str(parsed.get("title") or "").strip()
        content = str(parsed.get("content") or "").strip()
        reminder = parsed.get("reminder") or None
        raw_tags = parsed.get("tags") or []
        tags = [t for t in raw_tags if t in ALLOWED_NOTE_TAGS]
        raw_folder = parsed.get("folder")
        folder = raw_folder if raw_folder in ALLOWED_NOTE_FOLDERS else None
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Note generation returned non-JSON output", extra={"raw": raw})
        title = next((line.strip() for line in raw.splitlines() if line.strip()), "")[:60]
        content = raw.strip()
        reminder = None
        tags = []
        folder = None

    return NoteGenerateResponse(
        title=title or "Без названия", content=content, reminder=reminder, tags=tags, folder=folder,
    )


# Внутренний вызов rag_service -> llm_service во время индексации документа (заполняет
# document_chapters.summary). Best-effort со стороны rag_service — сбой здесь не должен
# ронять весь ingestion.
@router.post("/chapter-summary", response_model=ChapterSummaryResponse)
async def generate_chapter_summary(
    request: ChapterSummaryRequest,
    agent: LeanRagAgent = Depends(get_lean_rag_agent),
) -> ChapterSummaryResponse:
    summary = await _call_llm_provider(
        agent.llm_provider.generate_chapter_summary(chapter_text=request.chapter_text),
        log_label="Chapter summary generation",
    )
    return ChapterSummaryResponse(summary=summary.strip())


# Тот же вызывающий (rag_service, best-effort) — синтезирует одно резюме документа
# из уже готовых саммари его глав, без повторной прогонки полного текста через LLM.
@router.post("/document-summary", response_model=DocumentSummaryResponse)
async def generate_document_summary(
    request: DocumentSummaryRequest,
    agent: LeanRagAgent = Depends(get_lean_rag_agent),
) -> DocumentSummaryResponse:
    summary = await _call_llm_provider(
        agent.llm_provider.generate_document_summary(chapter_summaries=request.chapter_summaries),
        log_label="Document summary generation",
    )
    return DocumentSummaryResponse(summary=summary.strip())


# Тот же вызывающий (rag_service, best-effort) — генерирует описание таблицы для
# семантического поиска (эмбеддится и уходит в Qdrant отдельной точкой), не для показа
# пользователю напрямую.
@router.post("/table-summary", response_model=TableSummaryResponse)
async def generate_table_summary(
    request: TableSummaryRequest,
    agent: LeanRagAgent = Depends(get_lean_rag_agent),
) -> TableSummaryResponse:
    summary = await _call_llm_provider(
        agent.llm_provider.generate_table_summary(table_text=request.table_text),
        log_label="Table summary generation",
    )
    return TableSummaryResponse(summary=summary.strip())