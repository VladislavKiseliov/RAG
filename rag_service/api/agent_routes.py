from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/rag", tags=["agent"])

DEFAULT_TIMEOUT = float(os.getenv("LLM_API_TIMEOUT", "60"))


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)


class AskResponse(BaseModel):
    answer: str


def _get_llm_config() -> tuple[str, dict, dict]:
    url = os.getenv("LLM_API_URL")
    if not url:
        raise HTTPException(status_code=500, detail="LLM_API_URL is not set")

    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("LLM_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict = {}
    model = os.getenv("LLM_MODEL")
    if model:
        payload["model"] = model

    return url, headers, payload


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
