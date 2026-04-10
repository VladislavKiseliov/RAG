from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException

from rag_service.api.schemas import AskResponse, AskRequest, SearchResponse, SearchRequest

router = APIRouter(prefix="/rag", tags=["agent"])

DEFAULT_TIMEOUT = float(os.getenv("LLM_API_TIMEOUT", "60"))


@router.post("/answer", response_model=AskResponse)
async def answer_question(request: AskRequest) -> AskResponse:
    url, headers, payload = _get_llm_config()
    payload = {**payload, "question": request.question}

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM API timeout")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"LLM API error: {exc}")

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="LLM API returned invalid JSON")

    answer = data.get("answer") or data.get("text") or data.get("response") or ""
    return AskResponse(answer=answer)


@router.post("/search", response_model=SearchResponse)
async def search_endpoint(payload: SearchRequest) -> SearchResponse:
    """Retrieve relevant chunks and return LLM answer grounded in document context."""
    doc_uuid: uuid.UUID | None = None
    if payload.doc_id:
        try:
            doc_uuid = uuid.UUID(payload.doc_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid doc_id")

    try:
        result = await _search_service.search(
            query=payload.query,
            top_k=payload.top_k,
            doc_id=doc_uuid,
            score_threshold=payload.score_threshold,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Search pipeline failed: {exc}")

    return SearchResponse(**result)