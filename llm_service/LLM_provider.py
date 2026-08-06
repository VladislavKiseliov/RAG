from __future__ import annotations

import asyncio
from datetime import date
from typing import AsyncIterator, Callable, Coroutine, Protocol

from llm_service.ai_config import get_live_config
from llm_service.application.lean_rag_models import FinalPromptData
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.llm_provider")

TTFT_TIMEOUT_S = 30.0  # время до первого чанка от апстрима, на попытку
STREAM_MAX_RETRIES = 3
# 502/503/504 - типично временные сбои гейтвея/прокси (перегрузка, рестарт) - в отличие
# от остальных 4xx/5xx (невалидный запрос, лимит, нет ключа), их есть смысл ретраить.
TRANSIENT_STATUS_CODES = {502, 503, 504}


async def _stream_completion_with_retry(
    create_completion: Callable[[], Coroutine],
) -> AsyncIterator[str]:
    """Общая retry-логика стриминга chat-completion (переиспользуется обоими
    OpenAI-совместимыми провайдерами). Три точки обрыва SSE от апстрима:

    - до первого чанка (TTFT-таймаут/обрыв соединения) - безопасно ретраить с backoff
      (1с/2с/4с), пользователь ещё ничего не увидел;
    - после первого чанка (обрыв посреди генерации) - НЕ ретраим: повторный вызов начал бы
      новую, не связанную с уже показанной генерацию поверх уже отданных токенов. Исключение
      пробрасывается наверх как есть - вызывающий (LeanRagAgent.run_stream) помечает уже
      накопленный частичный ответ как прерванный, не теряет его;
    - на финальном чанке (finish_reason != stop, напр. content_filter/length) - не обрыв
      связи, а решение провайдера; ретрай не поможет, дописываем короткую пометку и
      завершаем генератор штатно, без исключения.

    create_completion: () -> awaitable создания стрима (chat.completions.create(stream=True)).
    4xx и не-транзиентные 5xx (APIStatusError вне TRANSIENT_STATUS_CODES) не ретраим вообще -
    ретрай не поможет (невалидный запрос/лимит/нет ключа, либо системный сбой у гейтвея,
    как было с gatellm.ru при stream=true - там падало 100% попыток, а не иногда).
    """
    from openai import APIConnectionError, APIStatusError, APITimeoutError

    for attempt in range(STREAM_MAX_RETRIES):
        first_delta_yielded = False
        stream = None
        try:
            stream = await asyncio.wait_for(create_completion(), timeout=TTFT_TIMEOUT_S)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta.content
                if delta:
                    first_delta_yielded = True
                    yield delta
                if choice.finish_reason and choice.finish_reason != "stop":
                    yield f"\n\n_[ответ обрезан провайдером: {choice.finish_reason}]_"
                    return
            return
        except (APIConnectionError, APITimeoutError, asyncio.TimeoutError, APIStatusError) as exc:
            if isinstance(exc, APIStatusError) and exc.status_code not in TRANSIENT_STATUS_CODES:
                raise
            if first_delta_yielded:
                raise
            if attempt == STREAM_MAX_RETRIES - 1:
                raise
            logger.warning(
                "LLM stream TTFT failed (attempt %d/%d), retrying: %s",
                attempt + 1, STREAM_MAX_RETRIES, exc,
            )
            await asyncio.sleep(2 ** attempt)
            continue
        finally:
            # AsyncStream.close() из openai SDK самовызывается только при полном прочтении
            # до конца (см. её докстринг) - если мы уходим раньше (finish_reason, retry,
            # исключение, либо нас отменили снаружи через CancelledError - см.
            # with_cancellation/LeanRagAgent.run_stream), соединение к апстриму иначе
            # держится открытым до сборки мусора вместо немедленного освобождения.
            if stream is not None:
                await stream.close()

# История диалога больше не вклеивается сюда текстом - отдельные role-сообщения
# (см. _history_to_messages/_build_answer_messages ниже), как того требует нативный
# chat-формат LLM API (границы реплик - по структуре запроса, не по нашей текстовой
# разметке; побочный эффект - старые реплики становятся стабильным префиксом messages,
# что вскрывает возможность кэширования промпта на стороне провайдера, если тот его
# поддерживает). Этот шаблон - только "текущий ход": то, что меняется каждый вызов.
CURRENT_TURN_TEMPLATE = """РЕЗЮМЕ ПРЕДЫДУЩЕЙ БЕСЕДЫ (то, что не вошло в историю выше):
{summary}

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


def _history_to_messages(chat_history: list[dict[str, str]]) -> list[dict[str, str]]:
    """[{"role": ..., "content": ...}, ...] из state.messages как есть -> role-сообщения
    для LLM API. role по умолчанию "user" (тот же дефолт, что и в agent/formatters.py
    ::format_chat_history, для консистентности при отсутствующем/пустом role)."""
    return [{"role": m.get("role") or "user", "content": m.get("content", "")} for m in chat_history]


def _build_answer_messages(current_query: str, data_prompt: FinalPromptData) -> list[dict]:
    """Общая сборка messages для чат-ответа (RAG/chat route) - переиспользуется
    OpenAICompatLLMProvider и GroqLLMProvider, раньше это был дословный дубль кода
    в обоих классах. system + история диалога отдельными role-сообщениями (не текстом,
    см. CURRENT_TURN_TEMPLATE) + последнее user-сообщение с summary/контекстом/вопросом."""
    config = get_live_config()

    if data_prompt.route == "domain_rag":
        system = config.prompts.system_prompt_rag
        context = data_prompt.context
    else:
        system = config.prompts.system_prompt_chat
        context = "Поиск в базе знаний не производился за ненадобностью."

    return [
        {"role": "system", "content": system},
        *_history_to_messages(data_prompt.chat_history),
        {"role": "user", "content": CURRENT_TURN_TEMPLATE.format(
            summary=data_prompt.summary,
            context=context,
            current_query=current_query,
        )},
    ]


class LLMProvider(Protocol):
    async def generate(self, *, current_query: str, data_prompt: FinalPromptData) -> str: ...
    def generate_stream(self, *, current_query: str, data_prompt: FinalPromptData) -> AsyncIterator[str]: ...
    async def generate_general(self, *, query: str, context: str) -> str: ...
    async def generate_json_raw(self, *, query: str, temperature: float = 0.2) -> str: ...
    async def generate_summary(self, *, messages: list[dict], existing_summary: str = "") -> str: ...
    async def generate_note(self, *, raw_text: str) -> str: ...
    async def generate_chapter_summary(self, *, chapter_text: str) -> str: ...
    async def generate_document_summary(self, *, chapter_summaries: str) -> str: ...
    async def generate_table_summary(self, *, table_text: str) -> str: ...
    async def aclose(self) -> None: ...


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

    async def aclose(self) -> None:
        await self._client.close()

    @staticmethod
    def _answer_messages(current_query: str, data_prompt: FinalPromptData) -> list[dict]:
        return _build_answer_messages(current_query, data_prompt)

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
        см. LeanRagAgent.run_stream) вместо ожидания полного completion.

        Ретраи TTFT/обрыв посреди генерации/finish_reason - см. _stream_completion_with_retry."""
        config = get_live_config()

        async def create_completion():
            return await self._client.chat.completions.create(
                model=config.llm.model_name,
                messages=self._answer_messages(current_query, data_prompt),
                temperature=config.llm.temperature,
                stream=True,
            )

        async for delta in _stream_completion_with_retry(create_completion):
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

    async def generate_json_raw(self, *, query: str, temperature: float = 0.2) -> str:
        """Для LLMGateway.generate_json (plan/reflect) - system-сообщение про JSON-контракт,
        не про обычный чат (см. json_contract_system_prompt в ai_config.toml). Раньше эти
        вызовы шли через generate_general(), чей general_system_prompt ни слова не говорит
        про JSON и конфликтовал с "верни строго JSON" в user-сообщении.

        temperature - от вызывающего (LLMGateway.generate_json), не config.llm.temperature:
        JSON-контракты (plan/reflect) хотят низкую температуру для стабильности, разговорный
        generate() - свою. Раньше параметр принимался, но игнорировался (использовался
        config.llm.temperature безусловно) - молчаливое расхождение с сигнатурой."""
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=[
                {"role": "system", "content": config.prompts.json_contract_system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=temperature,
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

    async def generate_table_summary(self, *, table_text: str) -> str:
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm_summary.model_name,
            messages=[
                {"role": "system", "content": config.prompts.table_summary_system_prompt},
                {"role": "user", "content": table_text},
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

    async def aclose(self) -> None:
        await self._client.close()

    @staticmethod
    def _answer_messages(current_query: str, data_prompt: FinalPromptData) -> list[dict]:
        return _build_answer_messages(current_query, data_prompt)

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
        см. LeanRagAgent.run_stream) вместо ожидания полного completion.

        Ретраи TTFT/обрыв посреди генерации/finish_reason - см. _stream_completion_with_retry."""
        config = get_live_config()

        async def create_completion():
            return await self._client.chat.completions.create(
                model=config.llm.model_name,
                messages=self._answer_messages(current_query, data_prompt),
                temperature=config.llm.temperature,
                stream=True,
            )

        async for delta in _stream_completion_with_retry(create_completion):
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

    async def generate_json_raw(self, *, query: str, temperature: float = 0.2) -> str:
        """Для LLMGateway.generate_json (plan/reflect) - system-сообщение про JSON-контракт,
        не про обычный чат (см. json_contract_system_prompt в ai_config.toml). Раньше эти
        вызовы шли через generate_general(), чей general_system_prompt ни слова не говорит
        про JSON и конфликтовал с "верни строго JSON" в user-сообщении.

        temperature - от вызывающего (LLMGateway.generate_json), не config.llm.temperature:
        JSON-контракты (plan/reflect) хотят низкую температуру для стабильности, разговорный
        generate() - свою. Раньше параметр принимался, но игнорировался (использовался
        config.llm.temperature безусловно) - молчаливое расхождение с сигнатурой."""
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm.model_name,
            messages=[
                {"role": "system", "content": config.prompts.json_contract_system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=temperature,
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

    async def generate_table_summary(self, *, table_text: str) -> str:
        config = get_live_config()
        response = await self._client.chat.completions.create(
            model=config.llm_summary.model_name,
            messages=[
                {"role": "system", "content": config.prompts.table_summary_system_prompt},
                {"role": "user", "content": table_text},
            ],
            temperature=config.llm_summary.temperature,
        )
        return response.choices[0].message.content or ""


__all__ = [
    "LLMProvider",
    "OpenAICompatLLMProvider",
    "GroqLLMProvider",
]