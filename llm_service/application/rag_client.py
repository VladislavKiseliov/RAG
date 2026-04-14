from __future__ import annotations

import httpx

from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.rag_client")


class RagClient:
    def __init__(self, *, base_url: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip('/')
        self._timeout = timeout

    async def retrieve(self, *, query: str, doc_id: str | None) -> dict:
        payload = {"query": query}
        if doc_id is not None:
            payload["doc_id"] = doc_id

        url = f"{self._base_url}/documents/retrieve"
        logger.info("RAG request", extra={"url": url, "doc_id": doc_id})

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "RAG response error",
                extra={
                    "status": exc.response.status_code,
                    "body": exc.response.text,
                },
            )
            raise
        except httpx.RequestError as exc:
            logger.error("RAG request failed", extra={"error": str(exc)})
            raise

        return response.json()
