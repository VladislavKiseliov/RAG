from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

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
)
from llm_service.application.lean_rag_agent import LeanRagAgent
from llm_service.dependencies import get_lean_rag_agent
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.api")

router = APIRouter(prefix="/llm", tags=["llm"])

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
        logger.info("LLM request", extra={"query": json.dumps(request.query), "doc_id": request.doc_id})
        final_state = await agent.run(
            query=request.query,
            history_messages_db=request.history_messages,
            summary=request.summary,

        )
    except Exception as exc:
        # CancelledError (BaseException, не Exception) сюда не попадёт - при дисконнекте
        # клиента (см. with_cancellation) отвечать всё равно уже некому.
        logger.exception("LLM pipeline failed")
        raise HTTPException(status_code=502, detail=f"LLM pipeline failed: {exc}")

    answer_text = final_state["response_model"]
    retrieval_data = final_state.get("retrieval_data", [])
    sources = LeanRagAgent.build_sources(retrieval_data)

    result = {
        "answer": answer_text,
        "sources": sources,
        "context": None,
        "total": len(sources),
    }

    return AskResponse(**result)


@router.post("/answer/stream")
async def answer_question_stream(
    request: AskRequest,
    agent: LeanRagAgent = Depends(get_lean_rag_agent),
) -> StreamingResponse:
    """SSE-вариант /answer: status -> (token|ping)* -> sources -> done.

    HTTP-заголовки уходят до первого события, поэтому ошибка на любом этапе (в т.ч.
    после части токенов) не может стать HTTPException - вместо этого событие 'error',
    backend/фронт обрабатывают его сами (см. conversation_service.py/useAiChat.js).
    """
    logger.info("LLM stream request", extra={"query": json.dumps(request.query), "doc_id": request.doc_id})

    async def event_stream():
        try:
            async for event in agent.run_stream(
                query=request.query,
                history_messages_db=request.history_messages,
                summary=request.summary,
            ):
                payload = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: {event['event']}\ndata: {payload}\n\n"
        except Exception as exc:
            logger.exception("LLM stream pipeline failed")
            payload = json.dumps({"message": str(exc)}, ensure_ascii=False)
            yield f"event: error\ndata: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/summary", response_model=SummaryResponse)
async def summarize_messages(
    request: SummaryRequest,
    agent: LeanRagAgent = Depends(get_lean_rag_agent),
) -> SummaryResponse:
    try:
        summary = await agent.llm_provider.generate_summary(
            messages=request.messages,
            existing_summary=request.existing_summary,
        )
    except Exception as exc:
        logger.exception("Summary generation failed")
        raise HTTPException(status_code=502, detail=f"Summary generation failed: {exc}")

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
    try:
        raw = await agent.llm_provider.generate_note(raw_text=request.raw_text)
    except Exception as exc:
        logger.exception("Note generation failed")
        raise HTTPException(status_code=502, detail=f"Note generation failed: {exc}")

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
    try:
        summary = await agent.llm_provider.generate_chapter_summary(chapter_text=request.chapter_text)
    except Exception as exc:
        logger.exception("Chapter summary generation failed")
        raise HTTPException(status_code=502, detail=f"Chapter summary generation failed: {exc}")

    return ChapterSummaryResponse(summary=summary.strip())


# Тот же вызывающий (rag_service, best-effort) — синтезирует одно резюме документа
# из уже готовых саммари его глав, без повторной прогонки полного текста через LLM.
@router.post("/document-summary", response_model=DocumentSummaryResponse)
async def generate_document_summary(
    request: DocumentSummaryRequest,
    agent: LeanRagAgent = Depends(get_lean_rag_agent),
) -> DocumentSummaryResponse:
    try:
        summary = await agent.llm_provider.generate_document_summary(chapter_summaries=request.chapter_summaries)
    except Exception as exc:
        logger.exception("Document summary generation failed")
        raise HTTPException(status_code=502, detail=f"Document summary generation failed: {exc}")

    return DocumentSummaryResponse(summary=summary.strip())