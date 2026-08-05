from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, ValidationError

from llm_service.llm_gateway import LLMGateway


class _Schema(BaseModel):
    x: int


def make_gateway(generate_json_raw_side_effect=None, generate_json_raw_return=None):
    provider = MagicMock()
    if generate_json_raw_side_effect is not None:
        provider.generate_json_raw = AsyncMock(side_effect=generate_json_raw_side_effect)
    else:
        provider.generate_json_raw = AsyncMock(return_value=generate_json_raw_return)
    provider.generate = AsyncMock(return_value="answer")
    provider.generate_stream = MagicMock()
    return LLMGateway(llm_provider=provider), provider


@pytest.mark.asyncio
async def test_generate_delegates_to_provider():
    gateway, provider = make_gateway()
    result = await gateway.generate(current_query="q", data_prompt=MagicMock())
    assert result == "answer"
    provider.generate.assert_awaited_once()


def test_generate_stream_delegates_to_provider():
    gateway, provider = make_gateway()
    gateway.generate_stream(current_query="q", data_prompt=MagicMock())
    provider.generate_stream.assert_called_once()


@pytest.mark.asyncio
async def test_generate_json_succeeds_first_try():
    gateway, provider = make_gateway(generate_json_raw_return='{"x": 5}')
    result = await gateway.generate_json(schema=_Schema, prompt="give json")
    assert result == _Schema(x=5)
    assert provider.generate_json_raw.await_count == 1


@pytest.mark.asyncio
async def test_generate_json_strips_markdown_fence():
    gateway, _ = make_gateway(generate_json_raw_return='```json\n{"x": 7}\n```')
    result = await gateway.generate_json(schema=_Schema, prompt="give json")
    assert result == _Schema(x=7)


@pytest.mark.asyncio
async def test_generate_json_retries_exactly_once_on_invalid_json():
    gateway, provider = make_gateway(generate_json_raw_side_effect=["not json", '{"x": 9}'])
    result = await gateway.generate_json(schema=_Schema, prompt="give json")
    assert result == _Schema(x=9)
    assert provider.generate_json_raw.await_count == 2


@pytest.mark.asyncio
async def test_generate_json_raises_after_second_failure_no_infinite_retry():
    gateway, provider = make_gateway(generate_json_raw_side_effect=["not json", "still not json"])
    with pytest.raises(ValidationError):
        await gateway.generate_json(schema=_Schema, prompt="give json")
    assert provider.generate_json_raw.await_count == 2
