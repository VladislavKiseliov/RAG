from __future__ import annotations

import asyncio
from typing import Any

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
        self._base_url = base_url.rstrip('/')
        self._url = f"{self._base_url}/documents/retrieve"
        self.max_queries = max_queries
        # Один клиент на весь жизненный цикл сервиса — переиспользует connection
        # pool/keep-alive к rag_service, вместо нового TCP+TLS хендшейка на каждый
        # запрос. Закрывается в main.py::lifespan при остановке приложения.
        self._client = httpx.AsyncClient(timeout=timeout)
        # Реестр документов корпуса (doc_id -> сырые поля DocumentSummaryResponse из
        # rag_service: filename/s3key/status/chunk_count/size/has_summary/created_at) -
        # см. _get_document_registry().
        self._document_registry: dict[str, dict[str, Any]] | None = None
        self._document_registry_lock = asyncio.Lock()

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

    async def get_appendix(self, doc_id: str) -> str | None:
        """Текст приложений (ПРИЛОЖЕНИЕ N) документа - см. A21 в rag_service/ISSUES.md:
        приложения не проходят через ChapterSplitter/векторизацию, значит retrieve()
        их никогда не найдёт. Единственный способ - прямой запрос за уже извлечённым
        (но не проиндексированным) текстом. Best-effort как и остальные read-тулы:
        отсутствие приложений (`text: null`) или сбой запроса - оба возвращают None,
        не бросают исключение (см. get_appendix в tool_registry.py)."""
        url = f"{self._base_url}/documents/{doc_id}/appendices"
        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Appendix fetch failed", extra={"doc_id": doc_id, "status": exc.response.status_code},
            )
            return None
        except httpx.RequestError as exc:
            logger.warning("Appendix fetch request failed", extra={"doc_id": doc_id, "error": str(exc)})
            return None

        return response.json().get("text")

    async def _get_document_registry(self) -> dict[str, dict[str, Any]]:
        """Реестр всех документов корпуса, строится один раз лениво при первом реальном
        обращении (find_document_id_by_code/list_documents) - НЕ при старте сервиса.
        Сетевой вызов к rag_service на старте добавил бы ещё одну точку отказа запуска
        (тот же урок, что уже стоил падения старта на мёртвом ML-роутере, см. B4 в
        ISSUES.md) ради данных, которые нужны не каждому запросу. In-memory, без
        авто-обновления в течение жизни процесса - тот же паттерн, что
        AbbreviationExpander в rag_service (ручная перезагрузка, если корпус изменился
        после старта). Хранит только то, что отдаёт список (GET /documents) - filename,
        s3key, status, chunk_count, size, has_summary, created_at. Главы/детали документа
        (GET /documents/{doc_id}) сюда не входят - отдельный, более тяжёлый вызов на
        документ, которым сегодня никто не пользуется (get_chapter - всё ещё
        NotImplementedError-заглушка в tool_registry.py).

        Сбой запроса не кэшируется как пустой реестр - следующий вызов повторит попытку
        (в отличие от ML-роутера, здесь нет причины сдаваться навсегда: rag_service может
        просто ещё не подняться при старте llm_service)."""
        if self._document_registry is not None:
            return self._document_registry
        async with self._document_registry_lock:
            if self._document_registry is None:
                try:
                    response = await self._client.get(f"{self._base_url}/documents", params={"limit": 500})
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("Document registry build failed, will retry on next call", extra={"error": str(exc)})
                    return {}
                self._document_registry = {doc["doc_id"]: doc for doc in response.json()}
        return self._document_registry

    async def find_document_id_by_code(self, document_code: str) -> str | None:
        """Резолвит doc_id по названию/номеру документа (ГОСТ/СП/ПУЭ) - LLM на этапе
        planning знает только то, что назвал пользователь текстом, ни одного UUID из
        корпуса она никогда не видела. Подстрока по filename в уже построенном реестре
        (не fuzzy, регистронезависимо) - тот же матчинг, что раньше делал ilike-запрос
        к rag_service, только локально, без сетевого вызова на каждое обращение.
        Несколько совпадений - берём первое по порядку реестра, различать их LLM не
        просили. 0 совпадений - None, не исключение."""
        registry = await self._get_document_registry()
        needle = document_code.lower()
        for doc_id, doc in registry.items():
            if needle in doc.get("filename", "").lower():
                return doc_id
        return None

    async def list_documents(self) -> list[dict[str, Any]]:
        """Список всех документов корпуса (см. _get_document_registry) - для
        list_documents-тула в tool_registry.py."""
        registry = await self._get_document_registry()
        return list(registry.values())