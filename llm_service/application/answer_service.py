from __future__ import annotations

from llm_service.application.context_builder import build_context
from llm_service.application.rag_client import RagClient
from llm_service.LLM_provider import LLMProvider
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.answer_service")


def _should_use_rag(query: str, doc_id: str | None) -> bool:
    if doc_id:
        return True

    q = query.strip().lower()
    if not q:
        return False

    direct_intents = (
        "привет",
        "здравств",
        "добрый",
        "как дела",
        "кто ты",
        "что ты умеешь",
        "help",
        "помоги",
    )
    if any(token in q for token in direct_intents):
        return False

    rag_hints = (
        "документ",
        "раздел",
        "пункт",
        "приложение",
        "таблица",
        "рис",
        "рисунок",
        "страниц",
        "гост",
        "сто",
        "снип",
    )
    if any(token in q for token in rag_hints):
        return True

    return len(q.split()) >= 4


class AnswerService:
    def __init__(
        self,
        *,
        rag_client: RagClient,
        llm_provider: LLMProvider,
        max_context_chars: int = 12000,
    ) -> None:
        self._rag_client = rag_client
        self._llm_provider = llm_provider
        self._max_context_chars = max_context_chars

    async def answer(self, *, query: str, doc_id: str | None) -> dict:
        use_rag = _should_use_rag(query, doc_id)
        logger.info("Route decision", extra={"use_rag": use_rag})

        if not use_rag:
            answer = await self._llm_provider.generate_general(query=query)
            return {
                "answer": answer,
                "sources": [],
                "context": "",
                "total": 0,
            }

        result = await self._rag_client.retrieve(query=query, doc_id=doc_id)
        sources = result.get("items") or []
        context = build_context(sources, self._max_context_chars)
        logger.info(
            "Context built",
            extra={"sources": len(sources), "context_len": len(context)},
        )
        answer = await self._llm_provider.generate(query=query, context=context)

        return {
            "answer": answer,
            "sources": sources,
            "context": context,
            "total": len(sources),
        }
