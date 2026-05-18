from __future__ import annotations

from typing import Protocol

from llm_service.application.lean_rag_models import FinalPromptData

SYSTEM_PROMPT_RAG = """Ты — профессиональный технический ассистент лаборатории.
Твоя задача — ответить на вопрос, строго опираясь на предоставленный КОНТЕКСТ ИЗ ДОКУМЕНТАЦИИ.

Правила:
1) Используй только информацию из блока КОНТЕКСТ ИЗ ДОКУМЕНТАЦИИ.
2) ИСТОРИЮ ДИАЛОГА и РЕЗЮМЕ используй только для понимания того, о каких деталях шла речь ранее (например, модель прибора или настройки ШИМ), если они не указаны в самом вопросе.
3) Если в КОНТЕКСТЕ ИЗ ДОКУМЕНТАЦИИ нет прямого ответа на вопрос, ответь ровно одной фразой: "В предоставленном контексте ответа нет."
4) Не придумывай факты от себя. Выводи только текст ответа, без вступлений и приветствий."""


SYSTEM_PROMPT_CHAT = """Ты — профессиональный инженер-консультант. 
Сейчас идет свободное обсуждение задачи, поиск по базе документации не производился.

Правила:
1) Отвечай на вопрос, опираясь на ИСТОРИЮ ДИАЛОГА, РЕЗЮМЕ ПРЕДЫДУЩЕЙ БЕСЕДЫ и свои технические знания.
2) Будь лаконичен, точен и вежлив.
3) Выводи только текст ответа, без дежурных вступлений."""

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
    async def generate(self, *, current_query: str, data_prompt: FinalPromptData) -> str: ...
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

    async def generate(self, *, current_query: str, data_prompt: FinalPromptData) -> str:
        if data_prompt.route == "domain_rag":
            system = SYSTEM_PROMPT_RAG
            context = data_prompt.context
        else:
            system = SYSTEM_PROMPT_CHAT
            context = "Поиск в базе знаний не производился за ненадобностью."

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": USER_TEMPLATE.format(
                    summary=data_prompt.summary,
                    chat_history=data_prompt.chat_history,
                    context=context,
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
        if data_prompt.route == "domain_rag":
            system = SYSTEM_PROMPT_RAG
            context = data_prompt.context
        else:
            system = SYSTEM_PROMPT_CHAT
            context = "Поиск в базе знаний не производился за ненадобностью."

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": USER_TEMPLATE.format(
                    summary=data_prompt.summary,
                    chat_history=data_prompt.chat_history,
                    context=context,
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