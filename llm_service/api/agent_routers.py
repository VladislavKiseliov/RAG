from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from llm_service.api.schemas import AskRequest, AskResponse, SummaryRequest, SummaryResponse
from llm_service.application.lean_rag_agent import LeanRagAgent
from llm_service.dependencies import get_lean_rag_agent
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.api")

router = APIRouter(prefix="/llm", tags=["llm"])

@router.post("/answer", response_model=AskResponse)
async def answer_question(
    request: AskRequest,
    agent: LeanRagAgent = Depends(get_lean_rag_agent),
) -> AskResponse:
    try:
        logger.info("LLM request", extra={"query": json.dumps(request.query), "doc_id": request.doc_id})
        final_state = await agent.run(
            query=request.query,
            history_messages_db=request.history_massage,
            summary=request.summary,

        )
    except Exception as exc:
        logger.exception("LLM pipeline failed")
        raise HTTPException(status_code=502, detail=f"LLM pipeline failed: {exc}")

    answer_text = final_state["response_model"]
    retrieval_data = final_state.get("retrieval_data", [])

    sources = [
        {
            "doc_id": item.metadata.doc_id,
            "parent_id": item.metadata.parent_id,
            "page_num": item.metadata.page_num,
            "score": item.metadata.score,
            "text": item.parent_chunk,
            "child_chunks": [c.text for c in item.child_chunks],
            "headers": item.metadata.headers,
        }
        for item in retrieval_data
    ]

    result = {
        "answer": answer_text,
        "sources": sources,
        "context": None,
        "total": len(sources),
    }

    return AskResponse(**result)


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