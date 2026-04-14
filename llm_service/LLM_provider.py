from __future__ import annotations

import os
from typing import Protocol


SYSTEM_PROMPT = """Ты — профессиональный ассистент, специализирующийся на технической документации.
Твоя задача — извлечь ответ на заданный вопрос из предоставленного ниже контекста.

Правила:
1) Язык ответа: всегда отвечай по-русски.
2) Строгость: используй только информацию из контекста.
3) Если ответа нет: ответь только фразой: "В предоставленном контексте ответа нет."
4) Формат: выведи только текст ответа, без вступлений."""

USER_TEMPLATE = """КОНТЕКСТ:
---
{context}
---

ВОПРОС: {question}"""

GENERAL_SYSTEM_PROMPT = """Ты — полезный ассистент. Отвечай кратко и по делу.
Если не уверен — честно скажи, что информации недостаточно."""


class LLMProvider(Protocol):
    async def generate(self, *, query: str, context: str) -> str: ...
    async def generate_general(self, *, query: str) -> str: ...


def _get_api_key() -> str:
    for name in ("Gate_LLM_KEY", "GATE_LLM_KEY", "LLM_API_KEY", "OPENAI_API_KEY"):
        value = os.getenv(name)
        if value:
            return value.strip()
    return ""


class OpenAICompatLLMProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = "openai/gpt-4o-mini",
    ):
        if not api_key:
            raise ValueError("LLM API key is empty (Gate_LLM_KEY / GATE_LLM_KEY / LLM_API_KEY / OPENAI_API_KEY)")
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def generate(self, *, query: str, context: str) -> str:
        if not context.strip():
            return "Релевантный контекст не найден."

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(context=context, question=query)},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    async def generate_general(self, *, query: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": GENERAL_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content or ""


__all__ = [
    "LLMProvider",
    "OpenAICompatLLMProvider",
    "_get_api_key",
]
