from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from llm_service.api.schemas import AskRequest, AskResponse
from llm_service.application.agent_service import LlmLangGraphAgent
from llm_service.dependencies import get_langgraph_agent
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.api")

router = APIRouter(prefix="/llm", tags=["llm"])

@router.post("/answer", response_model=AskResponse)
async def answer_question(
    request: AskRequest,
    agent: LlmLangGraphAgent = Depends(get_langgraph_agent),
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

    answer_text = final_state["messages"][-1].content if final_state.get("messages") else ""
    context_text = "\n".join(final_state.get("context", []))

    result = {
        "answer": answer_text,
        "sources": [],
        "context": context_text if request.include_context else None,
        "total": 0,
    }

    return AskResponse(**result)
