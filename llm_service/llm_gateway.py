from __future__ import annotations

from typing import AsyncIterator, TypeVar

from pydantic import BaseModel, ValidationError

from llm_service.application.lean_rag_models import FinalPromptData
from llm_service.LLM_provider import LLMProvider
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.llm_gateway")

T = TypeVar("T", bound=BaseModel)

# Аддитивный слой поверх LLM_provider.py (см. ARCHITECTURE.md §6) - не переписывает
# семь именных методов LLMProvider, они остаются как есть для текущих вызывающих
# мест (chapter/document summary, note, general chat, RAG generate). Gateway
# добавляет три новых общих метода для новых JSON-контрактных нод (plan/reflect/
# post_actions, будущий judge). Fallback-цепочка между несколькими моделями - не
# реализована здесь: второй модели/провайдера пока не существует (см. ARCHITECTURE.md
# §10 шаг 2d) - generate/generate_stream/generate_json делегируют в единственный
# сконфигурированный LLMProvider без ретраев на другую модель.


class LLMGateway:
    def __init__(self, *, llm_provider: LLMProvider) -> None:
        self._llm_provider = llm_provider

    async def generate(self, *, current_query: str, data_prompt: FinalPromptData) -> str:
        return await self._llm_provider.generate(current_query=current_query, data_prompt=data_prompt)

    def generate_stream(self, *, current_query: str, data_prompt: FinalPromptData) -> AsyncIterator[str]:
        return self._llm_provider.generate_stream(current_query=current_query, data_prompt=data_prompt)

    async def generate_json(self, *, schema: type[T], prompt: str, temperature: float = 0.2) -> T:
        """Pydantic-валидация + 1 ретрай на том же провайдере - реальная реализация,
        не требует новой инфры (см. ARCHITECTURE.md §6). Вызывается plan_node/reflect_node
        (planning_nodes.py/retrieval_nodes.py) - 100% живого трафика графа проходит через
        plan_node. Использует generate_json_raw() провайдера (не generate_general()) -
        отдельный system-промпт про JSON-контракт, см. LLM_provider.py."""
        raw = await self._llm_provider.generate_json_raw(query=prompt, temperature=temperature)
        try:
            return schema.model_validate_json(_strip_markdown_fence(raw))
        except ValidationError as exc:
            logger.warning("generate_json: first attempt failed validation, retrying once", extra={"error": str(exc)})
            retry_prompt = (
                f"{prompt}\n\nПредыдущий ответ не прошёл валидацию схемы:\n{exc}\n"
                "Верни СТРОГО валидный JSON по той же схеме, без markdown-разметки."
            )
            raw_retry = await self._llm_provider.generate_json_raw(query=retry_prompt, temperature=temperature)
            return schema.model_validate_json(_strip_markdown_fence(raw_retry))


def _strip_markdown_fence(raw: str) -> str:
    """LLM иногда оборачивает JSON в ```json ... ``` несмотря на инструкцию - снимаем
    типовую markdown-обёртку перед парсингом."""
    text = raw.strip()
    if text.startswith("```"):
        text = text[3:]
        if text.startswith("json"):
            text = text[4:]
        if text.endswith("```"):
            text = text[: -len("```")]
    return text.strip()
