from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from llm_service.api.schemas import AskRequest, AskResponse
from llm_service.application.answer_service import AnswerService
from llm_service.infrastructure import build_answer_service

router = APIRouter(prefix="/llm", tags=["llm"])


def get_answer_service() -> AnswerService:
    return build_answer_service()


@router.post("/answer", response_model=AskResponse)
async def answer_question(
    request: AskRequest,
    answer_service: AnswerService = Depends(get_answer_service),
) -> AskResponse:
    try:
        print(request.query)
        result = await answer_service.answer(
            query=request.query,
            doc_id=request.doc_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM pipeline failed: {exc}")

    if not request.include_context:
        result["context"] = None

    return AskResponse(**result)
