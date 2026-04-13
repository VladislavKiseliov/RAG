from __future__ import annotations

from llm_service.application.context_builder import build_context
from llm_service.application.rag_client import RagClient
from llm_service.LLM_provider import LLMProvider


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
        result = await self._rag_client.retrieve(query=query, doc_id=doc_id)
        sources = result.get("items") or []
        context = build_context(sources, self._max_context_chars)
        answer = await self._llm_provider.generate(query=query, context=context)

        return {
            "answer": answer,
            "sources": sources,
            "context": context,
            "total": len(sources),
        }
