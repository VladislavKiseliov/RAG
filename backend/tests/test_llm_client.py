from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.services.ai import llm_client as llm_client_module
from backend.services.ai.llm_client import LLMClient
from backend.utils.exceptions import LLMError, LLMUnavailableError


def _make_client(*, post=None, stream=None):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    if post is not None:
        client.post = post
    if stream is not None:
        client.stream = stream
    return client


def _patch_async_client(monkeypatch, client):
    monkeypatch.setattr(llm_client_module.httpx, "AsyncClient", MagicMock(return_value=client))


@pytest.fixture
def service() -> LLMClient:
    return LLMClient("http://llm-service")


async def test_get_answer_success(monkeypatch, service):
    response = MagicMock(raise_for_status=MagicMock())
    response.json.return_value = {"answer": "42", "sources": [{"a": 1}], "degraded": False}
    client = _make_client(post=AsyncMock(return_value=response))
    _patch_async_client(monkeypatch, client)

    result = await service.get_answer("q", [], "summary")

    assert result == {"answer": "42", "sources": [{"a": 1}], "degraded": False}


async def test_get_answer_http_status_error_raises_llm_error(monkeypatch, service):
    err_response = MagicMock(status_code=500, text="failure")
    exc = httpx.HTTPStatusError("err", request=MagicMock(), response=err_response)
    response = MagicMock(raise_for_status=MagicMock(side_effect=exc))
    client = _make_client(post=AsyncMock(return_value=response))
    _patch_async_client(monkeypatch, client)

    with pytest.raises(LLMError):
        await service.get_answer("q", [], "summary")


async def test_get_answer_request_error_raises_unavailable(monkeypatch, service):
    client = _make_client(post=AsyncMock(side_effect=httpx.ConnectError("unreachable")))
    _patch_async_client(monkeypatch, client)

    with pytest.raises(LLMUnavailableError):
        await service.get_answer("q", [], "summary")


async def test_generate_note_success(monkeypatch, service):
    response = MagicMock(raise_for_status=MagicMock())
    response.json.return_value = {"title": "T", "content": "C", "tags": []}
    client = _make_client(post=AsyncMock(return_value=response))
    _patch_async_client(monkeypatch, client)

    result = await service.generate_note("raw text")

    assert result["title"] == "T"


async def test_get_summary_success(monkeypatch, service):
    response = MagicMock(raise_for_status=MagicMock())
    response.json.return_value = {"summary": "short summary"}
    client = _make_client(post=AsyncMock(return_value=response))
    _patch_async_client(monkeypatch, client)

    result = await service.get_summary(messages=[{"role": "user", "content": "hi"}])

    assert result == "short summary"


class _FakeStreamCtx:
    def __init__(self, lines):
        self._lines = lines

    async def __aenter__(self):
        response = MagicMock()
        response.raise_for_status = MagicMock()

        async def _aiter():
            for line in self._lines:
                yield line

        response.aiter_lines = _aiter
        return response

    async def __aexit__(self, *args):
        return False


async def test_stream_answer_yields_parsed_sse_events(monkeypatch, service):
    lines = [
        ":keep-alive",
        "event:status",
        'data:{"stage": "searching"}',
        "",
        "event:token",
        'data:{"text": "hi"}',
        "",
        "event:done",
        'data:{"answer": "hi", "degraded": false}',
        "",
    ]
    client = _make_client(stream=MagicMock(return_value=_FakeStreamCtx(lines)))
    _patch_async_client(monkeypatch, client)

    events = [event async for event in service.stream_answer("q", [], "summary")]

    names = [name for name, _ in events]
    assert names == ["ping", "status", "token", "done"]
    assert events[1] == ("status", {"stage": "searching"})
    assert events[2] == ("token", {"text": "hi"})
    assert events[3] == ("done", {"answer": "hi", "degraded": False})
