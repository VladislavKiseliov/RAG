from __future__ import annotations

from datetime import date
from typing import AsyncIterator, Protocol

from llm_service.ai_config import get_live_config
from llm_service.application.lean_rag_models import FinalPromptData

USER_TEMPLATE = """РЕЗЮМЕ ДИАЛОГА:
{summary}

ИСТОРИЯ ДИАЛОГА:
{chat_history}

КОНТЕКСТ ИЗ ДОКУМЕНТОВ:
---
{context}
---

ВОПРОС: {current_query}"""

SUMMARY_USER_TEMPLATE = """СУЩЕСТВУЮЩЕЕ РЕЗЮМЕ:
{existing_summary}

НОВЫЕ СООБЩЕНИЯ:
{history}

Напиши обновлённое резюме."""

NOTE_USER_TEMPLATE = """Сегодняшняя дата: {today}

ИСХОДНЫЙ ТЕКСТ:
{raw_text}"""


class LLMProvider(Protocol):
    async def generate(self, *, current_query: str, data_prompt: FinalPromptData) -> str: ...
    def generate_stream(self, *, current_query: str, data_prompt: FinalPromptData) -> AsyncIterator[str]: ...
    async def generate_general(self, *, query: str, context: str) -> str: ...
    async def generate_summary(self, *, messages: list[dict], existing_summary: str = "") -> str: ...
    async def generate_note(self, *, raw_text: str) -> str: ...
    async def generate_chapter_summary(self, *, chapter_text: str) -> str: ...
    async def generate_document_summary(self, *, chapter_summaries: str) -> str: ...


class OpenAICompatLLMProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
    ):
        if not api_key:
            raise ValueError("LLM_API_KEY is not set")
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=60.0)

    @staticmethod
    def _answer_messages(current_query: str, data_prompt: FinalPromptData) -> list[dict]:
        config = get_live_config()

        if data_prompt.route == "domain_rag":
            system = config.prompts.system_prompt_rag
            context = data_prompt.context
        else:
            system = config.prompts.system_prompt_chat
            context = "Поиск в базе знаний не производился за ненадобностью."

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": USER_TEMPLATE.format(
                summary=data_prompt.summary,
                chat_history=data_prompt.chat_history,
                context=context,
                current_query=current_query,
            )},
        ]

    async def generate(self, *, current_query: str, data_prompt: FinalPromptData) -> str:
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=self._answer_messages(current_query, data_prompt),
            temperature=config.llm.temperature,
        )
        return response.choices[0].message.content or ""

    async def generate_stream(self, *, current_query: str, data_prompt: FinalPromptData):
        """Стримит дельты финального ответа (SSE-контракт status->token->sources->done,
        см. LeanRagAgent.run_stream) вместо ожидания полного completion."""
        config = get_live_config()
        stream = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=self._answer_messages(current_query, data_prompt),
            temperature=config.llm.temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def generate_general(self, *, query: str, context: str) -> str:
        config = get_live_config()
        content = f"{context}\n\n{query}" if context.strip() else query
        response = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=[
                {"role": "system", "content": config.prompts.general_system_prompt},
                {"role": "user", "content": content},
            ],
            temperature=config.llm.temperature,
        )
        return response.choices[0].message.content or ""

    async def generate_summary(self, *, messages: list[dict], existing_summary: str = "") -> str:
        config = get_live_config()
        history = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
        response = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=[
                {"role": "system", "content": config.prompts.summary_system_prompt},
                {"role": "user", "content": SUMMARY_USER_TEMPLATE.format(
                    existing_summary=existing_summary or "отсутствует",
                    history=history,
                )},
            ],
            temperature=config.llm.temperature,
        )
        return response.choices[0].message.content or ""

    async def generate_note(self, *, raw_text: str) -> str:
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=[
                {"role": "system", "content": config.prompts.note_system_prompt},
                {"role": "user", "content": NOTE_USER_TEMPLATE.format(
                    today=date.today().isoformat(),
                    raw_text=raw_text,
                )},
            ],
            temperature=config.llm.temperature,
        )
        return response.choices[0].message.content or ""

    async def generate_chapter_summary(self, *, chapter_text: str) -> str:
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm_summary.model_name,
            messages=[
                {"role": "system", "content": config.prompts.chapter_summary_system_prompt},
                {"role": "user", "content": chapter_text},
            ],
            temperature=config.llm_summary.temperature,
        )
        return response.choices[0].message.content or ""

    async def generate_document_summary(self, *, chapter_summaries: str) -> str:
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm_summary.model_name,
            messages=[
                {"role": "system", "content": config.prompts.document_summary_system_prompt},
                {"role": "user", "content": chapter_summaries},
            ],
            temperature=config.llm_summary.temperature,
        )
        return response.choices[0].message.content or ""


class GroqLLMProvider:
    def __init__(self, *, api_key: str):
        if not api_key:
            raise ValueError("HF_TOKEN is not set")
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://router.huggingface.co/v1",
            timeout=60.0,
        )

    @staticmethod
    def _answer_messages(current_query: str, data_prompt: FinalPromptData) -> list[dict]:
        config = get_live_config()

        if data_prompt.route == "domain_rag":
            system = config.prompts.system_prompt_rag
            context = data_prompt.context
        else:
            system = config.prompts.system_prompt_chat
            context = "Поиск в базе знаний не производился за ненадобностью."

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": USER_TEMPLATE.format(
                summary=data_prompt.summary,
                chat_history=data_prompt.chat_history,
                context=context,
                current_query=current_query,
            )},
        ]

    async def generate(self, *, current_query: str, data_prompt: FinalPromptData) -> str:
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=self._answer_messages(current_query, data_prompt),
            temperature=config.llm.temperature,
        )
        return response.choices[0].message.content or ""

    async def generate_stream(self, *, current_query: str, data_prompt: FinalPromptData):
        """Стримит дельты финального ответа (SSE-контракт status->token->sources->done,
        см. LeanRagAgent.run_stream) вместо ожидания полного completion."""
        config = get_live_config()
        stream = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=self._answer_messages(current_query, data_prompt),
            temperature=config.llm.temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def generate_general(self, *, query: str, context: str) -> str:
        config = get_live_config()
        content = f"{context}\n\n{query}" if context.strip() else query
        response = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=[
                {"role": "system", "content": config.prompts.general_system_prompt},
                {"role": "user", "content": content},
            ],
            temperature=config.llm.temperature,
        )
        return response.choices[0].message.content or ""

    async def generate_summary(self, *, messages: list[dict], existing_summary: str = "") -> str:
        config = get_live_config()
        history = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
        response = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=[
                {"role": "system", "content": config.prompts.summary_system_prompt},
                {"role": "user", "content": SUMMARY_USER_TEMPLATE.format(
                    existing_summary=existing_summary or "отсутствует",
                    history=history,
                )},
            ],
            temperature=config.llm.temperature,
        )
        return response.choices[0].message.content or ""

    async def generate_note(self, *, raw_text: str) -> str:
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=[
                {"role": "system", "content": config.prompts.note_system_prompt},
                {"role": "user", "content": NOTE_USER_TEMPLATE.format(
                    today=date.today().isoformat(),
                    raw_text=raw_text,
                )},
            ],
            temperature=config.llm.temperature,
        )
        return response.choices[0].message.content or ""

    async def generate_chapter_summary(self, *, chapter_text: str) -> str:
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm_summary.model_name,
            messages=[
                {"role": "system", "content": config.prompts.chapter_summary_system_prompt},
                {"role": "user", "content": chapter_text},
            ],
            temperature=config.llm_summary.temperature,
        )
        return response.choices[0].message.content or ""

    async def generate_document_summary(self, *, chapter_summaries: str) -> str:
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm_summary.model_name,
            messages=[
                {"role": "system", "content": config.prompts.document_summary_system_prompt},
                {"role": "user", "content": chapter_summaries},
            ],
            temperature=config.llm_summary.temperature,
        )
        return response.choices[0].message.content or ""


__all__ = [
    "LLMProvider",
    "OpenAICompatLLMProvider",
    "GroqLLMProvider",
]