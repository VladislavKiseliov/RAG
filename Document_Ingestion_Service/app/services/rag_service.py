import os
from typing import Any, Dict, Optional

from langchain_google_genai import ChatGoogleGenerativeAI

from ..config import GEMINI_API_KEY, LLM_MODEL_NAME


_llm_cache: Optional[ChatGoogleGenerativeAI] = None


def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm_cache
    if _llm_cache is not None:
        return _llm_cache

    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    _llm_cache = ChatGoogleGenerativeAI(
        model=LLM_MODEL_NAME,
        google_api_key=api_key,
    )
    return _llm_cache


def _extract_answer(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part).strip()
    return str(content) if content is not None else ""


def run_rag(question: str, collection: Optional[str] = None) -> Dict[str, Any]:
    # _ = collection  # kept for backward compatibility with request schema

    if not question or not question.strip():
        return {"answer": "Please provide a valid question.", "sources": []}

    response = _get_llm().invoke(question)
    answer = _extract_answer(getattr(response, "content", ""))
    return {"answer": answer, "sources": []}
