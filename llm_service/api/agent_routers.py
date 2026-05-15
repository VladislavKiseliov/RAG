from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from llm_service.api.schemas import AskRequest, AskResponse
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
    context_text =  final_state.get("final_context")


    result = {
        "answer": answer_text,
        "sources": [],
        "context": context_text if request.include_context else None,
        "total":0,
    }

    return AskResponse(**result)