from typing import List, Dict

import httpx
from backend.settings import settings
from backend.utils.exceptions import LLMError, LLMUnavailableError
from backend.utils.logger_config import setup_logger

logger = setup_logger("backend.llm_client")

LLM_SERVICE_URL = settings.LLM_SERVICE_URL


async def get_llm_summary(messages: List[Dict], existing_summary: str = "") -> str:
    url = f"{LLM_SERVICE_URL.rstrip('/')}/llm/summary"
    payload = {"messages": messages, "existing_summary": existing_summary}

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("summary", "")
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM summary error {e.response.status_code}", extra={"body": e.response.text})
            raise LLMError(f"Summary failed: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"LLM summary network error: {e}")
            raise LLMUnavailableError()


async def get_llm_answer(question: str, history_messages: List[Dict], summary: str) -> dict:
    url = f"{LLM_SERVICE_URL.rstrip('/')}/llm/answer"
    payload = {"query": question, "history_messages": history_messages, "summary": summary}

    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=5.0)) as client:
        logger.info(f"Запрос к LLM сервису: {url}", extra={"query": question})
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return {
                "answer": data.get("answer", "Ответ не получен"),
                "sources": data.get("sources", [])
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"LLM answer error {e.response.status_code}", extra={"body": e.response.text})
            raise LLMError(f"LLM answer failed: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Ошибка сети при обращении к LLM: {str(e)}")
            raise LLMUnavailableError()