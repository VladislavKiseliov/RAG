from __future__ import annotations

import httpx
from llm_service.application.lean_rag_models import RetrievalResult, RetrieveItem
from llm_service.exceptions import RagResponseError, RagUnavailableError
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.retrieval_service")

class RetrievalService:
    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 30.0,
        max_queries: int = 6,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/documents/retrieve"
        self.max_queries = max_queries
        # Один клиент на весь жизненный цикл сервиса — переиспользует connection
        # pool/keep-alive к rag_service, вместо нового TCP+TLS хендшейка на каждый
        # запрос. Закрывается в main.py::lifespan при остановке приложения.
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def retrieve(self, expanded_queries: list[str],top_k_per_query:int = 3,max_parents:int = 6) -> RetrievalResult:
        payload = {
            "queries": expanded_queries[: self.max_queries],
            "top_k": top_k_per_query,
        }
        logger.info("RAG retrieve", extra={"payload": payload})

        try:
            response = await self._client.post(self._url, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "RAG response error",
                extra={"status": exc.response.status_code, "body": exc.response.text},
            )
            raise RagResponseError(f"RAG returned {exc.response.status_code}")
        except httpx.RequestError as exc:
            logger.error("RAG request failed", extra={"error": str(exc)})
            raise RagUnavailableError(str(exc))

        parsed = RetrievalResult.model_validate(response.json())
        raw_items = parsed.items
        total_items = parsed.total
        items = [RetrieveItem.model_validate(raw) for raw in raw_items[:max_parents]]

        return RetrievalResult(items=items, total=total_items)