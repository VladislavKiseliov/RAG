from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from llm_service.LLM_provider import STREAM_MAX_RETRIES, _stream_completion_with_retry


def make_chunk(content: str | None, finish_reason: str | None = None):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content), finish_reason=finish_reason)])


def make_connection_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "http://test"))


def make_status_error(status_code: int) -> APIStatusError:
    response = httpx.Response(status_code=status_code, request=httpx.Request("POST", "http://test"))
    return APIStatusError(f"status {status_code}", response=response, body=None)


async def collect(create_completion):
    return [delta async for delta in _stream_completion_with_retry(create_completion)]


class FakeStream:
    """Односторонний async-итератор чанков, опционально с ошибкой на конкретном индексе.

    close() - как у настоящего openai.AsyncStream - считает, сколько раз реально
    закрыли соединение, чтобы тесты могли проверить, что _stream_completion_with_retry
    не оставляет стрим висеть при retry/finish_reason/исключении."""

    def __init__(self, chunks, raise_after: int | None = None, error: Exception | None = None):
        self._chunks = chunks
        self._raise_after = raise_after
        self._error = error
        self._i = 0
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._raise_after is not None and self._i == self._raise_after:
            raise self._error
        if self._i >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._i]
        self._i += 1
        return chunk

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_yields_all_deltas_on_success():
    chunks = [make_chunk("Привет"), make_chunk(", мир"), make_chunk(None, finish_reason="stop")]

    async def create_completion():
        return FakeStream(chunks)

    assert await collect(create_completion) == ["Привет", ", мир"]


@pytest.mark.asyncio
async def test_retries_on_ttft_failure_then_succeeds(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop)

    attempts = {"n": 0}

    async def create_completion():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise make_connection_error()
        return FakeStream([make_chunk("ок")])

    result = await collect(create_completion)
    assert result == ["ок"]
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop)

    attempts = {"n": 0}

    async def create_completion():
        attempts["n"] += 1
        raise make_connection_error()

    with pytest.raises(APIConnectionError):
        await collect(create_completion)
    assert attempts["n"] == STREAM_MAX_RETRIES


@pytest.mark.asyncio
async def test_retries_on_transient_502_then_succeeds(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop)

    attempts = {"n": 0}

    async def create_completion():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise make_status_error(502)
        return FakeStream([make_chunk("готово")])

    assert await collect(create_completion) == ["готово"]
    assert attempts["n"] == 2


@pytest.mark.parametrize("status_code", [400, 401, 429, 500])
@pytest.mark.asyncio
async def test_does_not_retry_non_transient_status_codes(monkeypatch, status_code):
    monkeypatch.setattr("asyncio.sleep", _noop)

    attempts = {"n": 0}

    async def create_completion():
        attempts["n"] += 1
        raise make_status_error(status_code)

    with pytest.raises(APIStatusError):
        await collect(create_completion)
    assert attempts["n"] == 1  # без единой повторной попытки - ретрай тут не поможет


@pytest.mark.asyncio
async def test_does_not_retry_after_first_delta_yielded(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop)

    attempts = {"n": 0}

    async def create_completion():
        attempts["n"] += 1
        return FakeStream([make_chunk("часть ответа")], raise_after=1, error=make_connection_error())

    collected = []
    with pytest.raises(APIConnectionError):
        async for delta in _stream_completion_with_retry(create_completion):
            collected.append(delta)

    assert collected == ["часть ответа"]
    assert attempts["n"] == 1  # ни одной повторной попытки после того, как токен уже ушёл наружу


@pytest.mark.asyncio
async def test_finish_reason_content_filter_appends_note_without_raising():
    chunks = [make_chunk("часть"), make_chunk(None, finish_reason="content_filter")]

    async def create_completion():
        return FakeStream(chunks)

    result = await collect(create_completion)
    assert result[0] == "часть"
    assert "content_filter" in result[1]


@pytest.mark.asyncio
async def test_stream_is_closed_on_normal_completion():
    stream = FakeStream([make_chunk("ок"), make_chunk(None, finish_reason="stop")])

    async def create_completion():
        return stream

    await collect(create_completion)
    assert stream.closed is True


@pytest.mark.asyncio
async def test_stream_is_closed_when_finish_reason_ends_early():
    # Третий чанк не должен даже читаться - но стрим всё равно обязан закрыться.
    stream = FakeStream([make_chunk("часть"), make_chunk(None, finish_reason="content_filter"), make_chunk("лишнее")])

    async def create_completion():
        return stream

    await collect(create_completion)
    assert stream.closed is True


@pytest.mark.asyncio
async def test_stream_is_closed_on_mid_stream_failure(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop)
    stream = FakeStream([make_chunk("часть ответа")], raise_after=1, error=make_connection_error())

    async def create_completion():
        return stream

    with pytest.raises(APIConnectionError):
        async for _ in _stream_completion_with_retry(create_completion):
            pass

    assert stream.closed is True


@pytest.mark.asyncio
async def test_stream_is_closed_when_cancelled_while_waiting_for_next_chunk():
    # Воспроизводит реальный продакшн-сценарий: LeanRagAgent.run_stream отменяет
    # зависшую задачу __anext__() при обрыве клиента (см. cancellation.py/run_stream) -
    # стрим к апстриму должен закрыться СРАЗУ, а не только когда GC когда-нибудь доберётся.
    class HangingStream(FakeStream):
        async def __anext__(self):
            if self._i >= len(self._chunks):
                await asyncio.Event().wait()  # имитирует ожидание следующего чанка от сети
            return await super().__anext__()

    stream = HangingStream([make_chunk("часть")])

    async def create_completion():
        return stream

    gen = _stream_completion_with_retry(create_completion).__aiter__()
    assert await gen.__anext__() == "часть"

    task = asyncio.ensure_future(gen.__anext__())
    await asyncio.sleep(0.01)  # дать задаче реально подвиснуть на Event().wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert stream.closed is True


@pytest.mark.asyncio
async def test_timeout_error_before_first_chunk_is_retried(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _noop)

    attempts = {"n": 0}

    async def create_completion():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise APITimeoutError(request=httpx.Request("POST", "http://test"))
        return FakeStream([make_chunk("готово")])

    assert await collect(create_completion) == ["готово"]
    assert attempts["n"] == 2


async def _noop(*_args, **_kwargs):
    return None