from __future__ import annotations

import httpx

from llm_service.exceptions import RerankerResponseError, RerankerUnavailableError
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.reranker_service")


class RerankerService:
    """Клиент TEI-реранкера (bge-reranker-v2-m3, отдельный контейнер tei-reranker,
    см. ARCHITECTURE.md §6/§10 шаг 4). Тот же паттерн переиспользуемого httpx-клиента,
    что и RetrievalService."""

    def __init__(self, *, base_url: str, timeout: float = 10.0) -> None:
        self._url = f"{base_url.rstrip('/')}/rerank"
        # Один клиент на весь жизненный цикл сервиса - переиспользует connection pool,
        # закрывается в main.py::lifespan при остановке приложения.
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def rerank(self, *, query: str, texts: list[str]) -> list[dict]:
        """Возвращает [{"index": int, "score": float}, ...], отсортированные TEI по
        убыванию релевантности. Пустой texts - пустой результат без сетевого вызова."""
        if not texts:
            return []

        payload = {"query": query, "texts": texts, "raw_scores": False, "return_text": False}
        logger.info("Reranker request", extra={"query": query, "candidates": len(texts)})

        try:
            response = await self._client.post(self._url, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Reranker response error",
                extra={"status": exc.response.status_code, "body": exc.response.text},
            )
            raise RerankerResponseError(f"Reranker returned {exc.response.status_code}")
        except httpx.RequestError as exc:
            logger.error("Reranker request failed", extra={"error": str(exc)})
            raise RerankerUnavailableError(str(exc))

        return response.json()
