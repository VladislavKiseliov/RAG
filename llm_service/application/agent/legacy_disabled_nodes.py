"""Ноды/гейты, отключённые от графа при переходе на planner-first схему
(см. graph_builder.py). НЕ удалены - просто не подключены `add_node`/`add_edge`
в build_agent_graph(), чтобы часть старой схемы можно было вернуть, не
переписывая код этих нод заново. Каждая - методы, а не свободные функции: те,
что реально делали I/O (expand_queries_node/retrieve_multi_node), используют
self.llm_provider/self.retrieval_service.

route_node/decide_after_router (классификация smalltalk/domain_rag/out_of_domain
через MLQueryRouter, LogReg+e5) удалены 2026-08-06 вместе с query_router из
конструкторов - не просто отключены, а полностью выпилены: заявленная будущая
замена роутинга - KNN-кластеризация по эмбеддингам (обсуждалась отдельно, ещё не
реализована), не ревайвл ЭТОЙ реализации, так что держать её мёртвым грузом
"на всякий случай" не было смысла.
"""

from __future__ import annotations

import time
from typing import Any

from llm_service.ai_config import get_live_config
from llm_service.application.lean_rag_models import LeanAgentState, RetrievalResult
from llm_service.application.services.query_service import QueryExpansionService
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.lean_rag_agent")


class LegacyDisabledNodesMixin:
    async def expand_queries_node(self, state: LeanAgentState) -> dict[str, list[str]]:
        """Генерирует альтернативные формулировки запроса через LLM для улучшения recall."""
        started = time.perf_counter()
        query_expansion_prompt = get_live_config().prompts.query_expansion_prompt
        recent_history_str = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in state.messages
        )
        raw_expansion = (await self.llm_provider.generate_general(query=query_expansion_prompt.format(summary= state.summary,
                                                                                                      recent_history = recent_history_str,
                                                                                                      query = state.query),
                                                                  context="")).strip()
        expanded_pack = await QueryExpansionService.expand(original_query=state.query,
                                                           raw_query=raw_expansion)
        logger.info(
            "Expand queries finished",
            extra={
                "query": state.query,
                "expanded_queries_count": len(expanded_pack.queries),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return {"expanded_queries": expanded_pack.queries}

    async def retrieve_multi_node(self, state: LeanAgentState) -> dict[str, Any]:
        """Ищет релевантные чанки по всем формулировкам запроса и собирает контекст."""
        started = time.perf_counter()
        retrieval_result: RetrievalResult= await self.retrieval_service.retrieve(state.expanded_queries)

        logger.info(
            "Retrieve multi finished",
            extra={
                "query": state.query,
                "expanded_queries_count": len(state.expanded_queries),
                "retrieval_result": retrieval_result,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return {"retrieval_data": retrieval_result.items}

    async def personal_search_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА: search_notes/search_tasks ещё не реализованы (нет HTTP-клиента
        к backend, где живут заметки/задачи) - см. tool_registry.py. Недостижима живым
        трафиком - роутер не может вернуть route="personal" (нет обучающих примеров)."""
        return {"retrieval_data": []}

    async def resolve_docs_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА: определение набора документов из attachment'ов сообщения или
        матча по названию/коду не реализовано - AskRequest несёт только одиночный
        doc_id, не список attachment'ов (см. ARCHITECTURE.md §3). Недостижима живым
        трафиком - роутер не может вернуть route="complex"."""
        return {"resolved_docs": []}

    async def decide_after_resolve_docs(self, state: LeanAgentState) -> str:
        """Реальный код-гейт (без внешних зависимостей) - корректен уже сегодня, хотя
        и недостижим (resolve_docs_node-заглушка всегда отдаёт пустой список)."""
        max_docs_interactive = get_live_config().gateway.max_docs_interactive
        if not state.resolved_docs:
            return "clarify"
        if len(state.resolved_docs) > max_docs_interactive:
            return "background"
        return "gather_passports"

    async def clarify_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА, терминальная нода - недостижима (см. resolve_docs_node)."""
        return {"response_model": "Уточните, пожалуйста, какие документы сравнить."}

    async def background_report_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА, терминальная нода - фоновый workflow для широкого сравнения
        (ARCHITECTURE.md §9/§10 шаг 8b) не реализован. Недостижима (см. resolve_docs_node)."""
        return {"response_model": "Широкое сравнение документов пока не реализовано."}

    async def gather_passports_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА: get_document_passport ещё не реализован в реестре инструментов.
        Недостижима (см. resolve_docs_node/decide_after_resolve_docs)."""
        return {"document_passports": []}
