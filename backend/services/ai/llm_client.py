import json
from typing import AsyncIterator, List, Dict

import httpx

from backend.utils.exceptions import LLMError, LLMUnavailableError
from backend.utils.logger_config import setup_logger

logger = setup_logger("backend.llm_client")


class LLMClient:
    def __init__(self, service_url: str) -> None:
        self._base_url = service_url.rstrip("/")

    async def stream_answer(
        self, question: str, history_messages: List[Dict], summary: str
    ) -> AsyncIterator[tuple[str, dict]]:
        """SSE-вариант get_answer(): отдаёт (event_name, data) по мере поступления от llm_service.

        Контракт событий (см. llm_service/api/agent_routers.py::answer_question_stream):
        status -> token* -> sources -> done, либо error на любом этапе.
        """
        url = f"{self._base_url}/llm/answer/stream"
        payload = {"query": question, "history_messages": history_messages, "summary": summary}

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=5.0)) as client:
                async with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    event_name: str | None = None
                    data_lines: list[str] = []
                    async for line in response.aiter_lines():
                        if line == "":
                            if event_name is not None:
                                data = json.loads("\n".join(data_lines)) if data_lines else {}
                                yield event_name, data
                            event_name, data_lines = None, []
                            continue
                        if line.startswith("event:"):
                            event_name = line[len("event:"):].strip()
                        elif line.startswith("data:"):
                            data_lines.append(line[len("data:"):].strip())
        except httpx.HTTPStatusError as e:
            logger.error("LLM stream answer error %s", e.response.status_code)
            raise LLMError(f"LLM stream answer failed: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error("LLM service unreachable: %s", str(e))
            raise LLMUnavailableError()

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

    async def generate_note(self, raw_text: str) -> dict:
        url = f"{self._base_url}/llm/note"
        payload = {"raw_text": raw_text}

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("LLM note generation error %s", e.response.status_code, extra={"body": e.response.text})
                raise LLMError(f"Note generation failed: {e.response.text}")
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