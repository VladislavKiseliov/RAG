from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from llm_service.api.schemas import AskRequest, AskResponse
from llm_service.application.answer_service import AnswerService
from llm_service.infrastructure import build_answer_service
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.api")

router = APIRouter(prefix="/llm", tags=["llm"])


def get_answer_service() -> AnswerService:
    return build_answer_service()


@router.post("/answer", response_model=AskResponse)
async def answer_question(
    request: AskRequest,
    answer_service: AnswerService = Depends(get_answer_service),
) -> AskResponse:
    try:
        logger.info("LLM request", extra={"query": json.dumps(request.query), "doc_id": request.doc_id})
        result = await answer_service.answer(
            query=request.query,
            doc_id=request.doc_id,
        )
    except Exception as exc:
        logger.exception("LLM pipeline failed")
        raise HTTPException(status_code=502, detail=f"LLM pipeline failed: {exc}")

    if not request.include_context:
        result["context"] = None

    return AskResponse(**result)
