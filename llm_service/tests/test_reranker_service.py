from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from llm_service.application.services.reranker_service import RerankerService
from llm_service.exceptions import RerankerResponseError, RerankerUnavailableError


def make_service(base_url: str = "http://tei-reranker:80") -> RerankerService:
    return RerankerService(base_url=base_url, timeout=5.0)


def _mock_response(body, status_code: int = 200) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = body
    mock_resp.raise_for_status = MagicMock()
    mock_resp.status_code = status_code
    return mock_resp


class TestServiceConfig:
    def test_url_built_from_base_url(self):
        service = make_service(base_url="http://tei-reranker:80")
        assert service._url == "http://tei-reranker:80/rerank"

    def test_trailing_slash_stripped(self):
        service = make_service(base_url="http://tei-reranker:80/")
        assert service._url == "http://tei-reranker:80/rerank"


class TestRerankSuccess:
    @pytest.mark.asyncio
    async def test_returns_scored_indices(self):
        service = make_service()
        raw = [{"index": 1, "score": 0.9}, {"index": 0, "score": 0.2}]
        service._client.post = AsyncMock(return_value=_mock_response(raw))

        result = await service.rerank(query="вопрос", texts=["a", "b"])

        assert result == raw

    @pytest.mark.asyncio
    async def test_sends_query_and_texts_in_payload(self):
        service = make_service()
        captured = {}

        def capture_post(url, json):
            captured["payload"] = json
            return _mock_response([])

        service._client.post = AsyncMock(side_effect=capture_post)

        await service.rerank(query="мой вопрос", texts=["текст1", "текст2"])

        assert captured["payload"]["query"] == "мой вопрос"
        assert captured["payload"]["texts"] == ["текст1", "текст2"]
        assert captured["payload"]["raw_scores"] is False

    @pytest.mark.asyncio
    async def test_empty_texts_skips_network_call(self):
        service = make_service()
        service._client.post = AsyncMock()

        result = await service.rerank(query="вопрос", texts=[])

        assert result == []
        service._client.post.assert_not_called()


class TestRerankErrors:
    @pytest.mark.asyncio
    async def test_http_500_raises_reranker_response_error(self):
        service = make_service()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )
        service._client.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(RerankerResponseError):
            await service.rerank(query="вопрос", texts=["a"])

    @pytest.mark.asyncio
    async def test_connection_error_raises_reranker_unavailable(self):
        service = make_service()
        service._client.post = AsyncMock(side_effect=httpx.RequestError("connection refused"))

        with pytest.raises(RerankerUnavailableError):
            await service.rerank(query="вопрос", texts=["a"])
