from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
import httpx

from llm_service.application.services.retrieval_service import RetrievalService
from llm_service.exceptions import RagResponseError, RagUnavailableError


def make_service(base_url: str = "http://rag:8001", max_queries: int = 6) -> RetrievalService:
    return RetrievalService(base_url=base_url, timeout=5.0, max_queries=max_queries)


def make_raw_response(items: list[dict] | None = None, total: int = 0) -> dict:
    return {"items": items or [], "total": total}


def make_raw_item(parent_chunk: str = "текст раздела") -> dict:
    return {
        "parent_chunk": parent_chunk,
        "child_chunks": [{"text": "дочерний чанк", "score": 0.9}],
        "metadata": {
            "doc_id": "doc-1",
            "parent_id": "parent-1",
            "score": 0.9,
            "headers": {},
        },
    }


# ---------------------------------------------------------------------------
# Конфигурация сервиса
# ---------------------------------------------------------------------------

class TestServiceConfig:
    def test_url_built_from_base_url(self):
        service = make_service(base_url="http://rag:8001")
        assert service._url == "http://rag:8001/documents/retrieve"

    def test_trailing_slash_stripped(self):
        service = make_service(base_url="http://rag:8001/")
        assert service._url == "http://rag:8001/documents/retrieve"

    def test_max_queries_stored(self):
        service = make_service(max_queries=4)
        assert service.max_queries == 4


# ---------------------------------------------------------------------------
# retrieve — успешный ответ
# ---------------------------------------------------------------------------

class TestRetrieveSuccess:
    def _mock_response(self, body: dict, status_code: int = 200) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.json.return_value = body
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = status_code
        return mock_resp

    @pytest.mark.asyncio
    async def test_returns_retrieval_result(self):
        service = make_service()
        raw = make_raw_response(items=[make_raw_item()], total=1)
        service._client.post = AsyncMock(return_value=self._mock_response(raw))

        result = await service.retrieve(["запрос"])

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].parent_chunk == "текст раздела"

    @pytest.mark.asyncio
    async def test_queries_truncated_to_max_queries(self):
        service = make_service(max_queries=3)
        raw = make_raw_response()
        captured = {}

        def capture_post(url, json):
            captured["payload"] = json
            mock_resp = MagicMock()
            mock_resp.json.return_value = raw
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        service._client.post = AsyncMock(side_effect=capture_post)

        await service.retrieve(["q1", "q2", "q3", "q4", "q5"])

        assert len(captured["payload"]["queries"]) == 3

    @pytest.mark.asyncio
    async def test_max_parents_limits_items(self):
        service = make_service()
        items = [make_raw_item(f"раздел {i}") for i in range(10)]
        raw = make_raw_response(items=items, total=10)
        service._client.post = AsyncMock(return_value=self._mock_response(raw))

        result = await service.retrieve(["запрос"], max_parents=4)

        assert len(result.items) == 4

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_items(self):
        service = make_service()
        raw = make_raw_response(items=[], total=0)
        service._client.post = AsyncMock(return_value=self._mock_response(raw))

        result = await service.retrieve(["запрос"])

        assert result.items == []
        assert result.total == 0


# ---------------------------------------------------------------------------
# retrieve — ошибки
# ---------------------------------------------------------------------------

class TestRetrieveErrors:
    @pytest.mark.asyncio
    async def test_http_500_raises_rag_response_error(self):
        service = make_service()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )
        service._client.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(RagResponseError):
            await service.retrieve(["запрос"])

    @pytest.mark.asyncio
    async def test_connection_error_raises_rag_unavailable(self):
        service = make_service()
        service._client.post = AsyncMock(
            side_effect=httpx.RequestError("connection refused")
        )

        with pytest.raises(RagUnavailableError):
            await service.retrieve(["запрос"])


# ---------------------------------------------------------------------------
# Реестр документов (find_document_id_by_code / list_documents) - построен один раз
# лениво при первом обращении, кэшируется в памяти на весь процесс.
# ---------------------------------------------------------------------------

def _mock_get_response(body, status_code: int = 200) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = body
    mock_resp.raise_for_status = MagicMock()
    mock_resp.status_code = status_code
    return mock_resp


class TestDocumentRegistry:
    @pytest.mark.asyncio
    async def test_find_document_id_by_code_matches_filename_substring(self):
        service = make_service()
        docs = [
            {"doc_id": "d1", "filename": "СП 1.13130 Эвакуационные пути.pdf"},
            {"doc_id": "d2", "filename": "ГОСТ 12.1.004.pdf"},
        ]
        service._client.get = AsyncMock(return_value=_mock_get_response(docs))

        result = await service.find_document_id_by_code("СП 1.13130")

        assert result == "d1"

    @pytest.mark.asyncio
    async def test_find_document_id_by_code_case_insensitive(self):
        service = make_service()
        docs = [{"doc_id": "d1", "filename": "СП 1.13130.pdf"}]
        service._client.get = AsyncMock(return_value=_mock_get_response(docs))

        result = await service.find_document_id_by_code("сп 1.13130")

        assert result == "d1"

    @pytest.mark.asyncio
    async def test_find_document_id_by_code_no_match_returns_none(self):
        service = make_service()
        docs = [{"doc_id": "d1", "filename": "ГОСТ 12.1.004.pdf"}]
        service._client.get = AsyncMock(return_value=_mock_get_response(docs))

        result = await service.find_document_id_by_code("несуществующий документ")

        assert result is None

    @pytest.mark.asyncio
    async def test_registry_built_only_once_across_multiple_calls(self):
        # Второй find_document_id_by_code (и любой list_documents) не должен снова
        # ходить в сеть - реестр кэшируется в памяти после первой успешной сборки.
        service = make_service()
        docs = [{"doc_id": "d1", "filename": "СП 1.13130.pdf"}]
        service._client.get = AsyncMock(return_value=_mock_get_response(docs))

        await service.find_document_id_by_code("СП 1.13130")
        await service.find_document_id_by_code("СП 1.13130")
        await service.list_documents()

        assert service._client.get.await_count == 1

    @pytest.mark.asyncio
    async def test_list_documents_returns_all_cached_entries(self):
        service = make_service()
        docs = [
            {"doc_id": "d1", "filename": "СП 1.13130.pdf"},
            {"doc_id": "d2", "filename": "ГОСТ 12.1.004.pdf"},
        ]
        service._client.get = AsyncMock(return_value=_mock_get_response(docs))

        result = await service.list_documents()

        assert len(result) == 2
        assert {d["doc_id"] for d in result} == {"d1", "d2"}

    @pytest.mark.asyncio
    async def test_registry_build_failure_is_not_cached_and_retries_next_call(self):
        # В отличие от мёртвого ML-роутера (best-effort, сдаётся навсегда), здесь есть
        # смысл повторить попытку - rag_service мог просто ещё не подняться.
        service = make_service()
        docs = [{"doc_id": "d1", "filename": "СП 1.13130.pdf"}]
        service._client.get = AsyncMock(
            side_effect=[httpx.RequestError("connection refused"), _mock_get_response(docs)]
        )

        first = await service.find_document_id_by_code("СП 1.13130")
        second = await service.find_document_id_by_code("СП 1.13130")

        assert first is None
        assert second == "d1"
        assert service._client.get.await_count == 2