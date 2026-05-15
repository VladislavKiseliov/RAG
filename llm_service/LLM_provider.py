from __future__ import annotations

from typing import Protocol

from llm_service.application.lean_rag_models import FinalPromptData

SYSTEM_PROMPT = """Ты — профессиональный ассистент, специализирующийся на технической документации.
Твоя задача — извлечь ответ на заданный вопрос из предоставленного ниже контекста.

Правила:
1) Язык ответа: всегда отвечай по-русски.
2) Строгость: используй только информацию из контекста.
3) Если ответа нет: ответь только фразой: "В предоставленном контексте ответа нет."
4) Формат: выведи только текст ответа, без вступлений."""

USER_TEMPLATE = """РЕЗЮМЕ ДИАЛОГА:
{summary}

ИСТОРИЯ ДИАЛОГА:
{chat_history}

КОНТЕКСТ ИЗ ДОКУМЕНТОВ:
---
{context}
---

ВОПРОС: {current_query}"""

GENERAL_SYSTEM_PROMPT = """Ты — полезный ассистент. Отвечай кратко и по делу.
Если не уверен — честно скажи, что информации недостаточно."""


class LLMProvider(Protocol):
    async def generate(self, *, summary: str, chat_history: str, context: str, current_query: str) -> str: ...
    async def generate_general(self, *, query: str, context: str) -> str: ...


class OpenAICompatLLMProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str = "openai/gpt-4o-mini",
    ):
        if not api_key:
            raise ValueError("LLM_API_KEY is not set")
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=60.0)
        self._model = model

    async def generate(self, *, current_query:str, data_prompt: FinalPromptData) -> str:

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(
                    summary=data_prompt.summary,
                    chat_history=data_prompt.chat_history,
                    context=data_prompt.context,
                    current_query=current_query,
                )},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    async def generate_general(self, *, query: str, context: str) -> str:
        print(1)
        content = f"{context}\n\n{query}" if context.strip() else query
        print(2)
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": GENERAL_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content or ""


class GroqLLMProvider:
    def __init__(self, *, api_key: str, model: str = "openai/gpt-oss-120b:groq"):
        if not api_key:
            raise ValueError("HF_TOKEN is not set")
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://router.huggingface.co/v1",
            timeout=60.0,
        )
        self._model = model

    async def generate(self, *, current_query: str, data_prompt: FinalPromptData) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_TEMPLATE.format(
                    summary=data_prompt.summary,
                    chat_history=data_prompt.chat_history,
                    context=data_prompt.context,
                    current_query=current_query,
                )},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    async def generate_general(self, *, query: str, context: str) -> str:
        content = f"{context}\n\n{query}" if context.strip() else query
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": GENERAL_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content or ""


__all__ = [
    "LLMProvider",
    "OpenAICompatLLMProvider",
    "GroqLLMProvider",
]