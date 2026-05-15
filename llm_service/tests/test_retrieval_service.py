from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=self._mock_response(raw))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

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

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=capture_post)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await service.retrieve(["q1", "q2", "q3", "q4", "q5"])

        assert len(captured["payload"]["queries"]) == 3

    @pytest.mark.asyncio
    async def test_max_parents_limits_items(self):
        service = make_service()
        items = [make_raw_item(f"раздел {i}") for i in range(10)]
        raw = make_raw_response(items=items, total=10)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=self._mock_response(raw))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await service.retrieve(["запрос"], max_parents=4)

        assert len(result.items) == 4

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_items(self):
        service = make_service()
        raw = make_raw_response(items=[], total=0)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=self._mock_response(raw))
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

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

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(RagResponseError):
                await service.retrieve(["запрос"])

    @pytest.mark.asyncio
    async def test_connection_error_raises_rag_unavailable(self):
        service = make_service()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.RequestError("connection refused")
            )
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(RagUnavailableError):
                await service.retrieve(["запрос"])