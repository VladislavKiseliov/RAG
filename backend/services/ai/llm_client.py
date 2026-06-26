from typing import List, Dict

import httpx

from backend.utils.exceptions import LLMError, LLMUnavailableError
from backend.utils.logger_config import setup_logger

logger = setup_logger("backend.llm_client")


class LLMClient:
    def __init__(self, service_url: str) -> None:
        self._base_url = service_url.rstrip("/")

    async def get_answer(self, question: str, history_messages: List[Dict], summary: str) -> dict:
        url = f"{self._base_url}/llm/answer"
        payload = {"query": question, "history_messages": history_messages, "summary": summary}

        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=5.0)) as client:
            logger.info("Sending answer request to LLM service", extra={"query": question})
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return {
                    "answer": data.get("answer", "Ответ не получен"),
                    "sources": data.get("sources", []),
                }
            except httpx.HTTPStatusError as e:
                logger.error("LLM answer error %s", e.response.status_code, extra={"body": e.response.text})
                raise LLMError(f"LLM answer failed: {e.response.text}")
            except httpx.RequestError as e:
                logger.error("LLM service unreachable: %s", str(e))
                raise LLMUnavailableError()

    async def get_summary(self, messages: List[Dict], existing_summary: str = "") -> str:
        url = f"{self._base_url}/llm/summary"
        payload = {"messages": messages, "existing_summary": existing_summary}

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json().get("summary", "")
            except httpx.HTTPStatusError as e:
                logger.error("LLM summary error %s", e.response.status_code, extra={"body": e.response.text})
                raise LLMError(f"Summary failed: {e.response.text}")
            except httpx.RequestError as e:
                logger.error("LLM service unreachable: %s", str(e))
                raise LLMUnavailableError()