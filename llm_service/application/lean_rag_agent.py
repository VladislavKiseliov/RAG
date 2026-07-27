from __future__ import annotations

import asyncio
import time
from typing import Any

from langgraph.graph import END, StateGraph


from llm_service.ai_config import get_live_config
from llm_service.LLM_provider import OpenAICompatLLMProvider
from llm_service.application.lean_rag_models import LeanAgentState, QueryRouterProtocol, RetrievalResult, \
    FinalPromptData, RetrieveItem
from llm_service.application.services.query_service import QueryExpansionService
from llm_service.application.services.retrieval_service import  RetrievalService
from llm_service.utils.logger_config import setup_logger


logger = setup_logger("llm_service.lean_rag_agent")


class LeanRagAgent:
    def __init__(
        self,
        *,
        llm_provider: OpenAICompatLLMProvider,
        query_router: QueryRouterProtocol,
        retrieval_service: RetrievalService,
    ) -> None:
        self.llm_provider = llm_provider
        self.query_router = query_router
        self.retrieval_service = retrieval_service
        self.app = self._build_graph()

        logger.info("Lean RAG agent initialized",)

    def _build_graph(self):
        """Собирает и компилирует LangGraph граф один раз при инициализации."""
        workflow = StateGraph(LeanAgentState)

        workflow.add_node("router", self.route_node)
        workflow.add_node("expand_queries", self.expand_queries_node)
        workflow.add_node("retrieve_multi", self.retrieve_multi_node)
        workflow.add_node("build_prompt", self.build_prompt_node)
        workflow.add_node("generate", self.generate_node)

        workflow.set_entry_point("router")
        workflow.add_conditional_edges(
            "router",
            self.decide_after_router,
            {
                "smalltalk": "build_prompt",
                "out_of_domain": "build_prompt",
                "expand": "expand_queries",
            },
        )
        workflow.add_edge("expand_queries", "retrieve_multi")
        workflow.add_edge("retrieve_multi", "build_prompt")
        workflow.add_edge("build_prompt", "generate")
        workflow.add_edge("generate", END)

        return workflow.compile()

    async def route_node(self, state: LeanAgentState) -> dict[str, str | list[str]]:
        """Определяет тип запроса: smalltalk / domain_rag / out_of_domain."""
        started = time.perf_counter()
        # .route() внутри синхронно гоняет SentenceTransformer.encode + predict_proba (CPU-bound) —
        # без to_thread это блокирует event loop на всё время эмбеддинга, стопоря остальные
        # параллельные запросы к сервису.
        route = await asyncio.to_thread(self.query_router.route, state.query)

        logger.info(
            "Router finished",
            extra={
                "route": route,
                "query": state.query,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return {"route": route}

    async def decide_after_router(self, state: LeanAgentState) -> str:
        """Выбирает следующий узел графа на основе route"""
        if state.route in {"smalltalk", "out_of_domain"}:
            return state.route

        return "expand"

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


    def _format_child_chunks_retrive_data(self, item: RetrieveItem) -> str:
        """[Документ: <filename> | Раздел <title>]\n<текст родительского чанка>.

        Раньше сюда шёл сырой Python-repr headers (`f"Раздел {item.metadata.headers}:..."`,
        то есть буквально "Раздел {'chapter_number': '2', 'title': '...'}" в промпте) и список
        child-чанков со скорами через запятую — не нужен LLM, только раздувал контекст.
        `title` уже содержит номер раздела впереди (напр. "2 Нормативные ссылки"), отдельно
        chapter_number не дублируем — та же логика, что в Message.jsx::formatName на фронте.
        """
        title = (item.metadata.headers or {}).get("title") or "без названия"
        doc_name = item.metadata.source or item.metadata.doc_id
        return f"[Документ: {doc_name} | Раздел {title}]\n{item.parent_chunk}"



    async def build_prompt_node(self, state: LeanAgentState) -> dict[str, Any]:
        started = time.perf_counter()

        context_str = "\n\n".join((self._format_child_chunks_retrive_data(item) for item in state.retrieval_data))
        history_str = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in state.messages
        )

        final_context = FinalPromptData(context=context_str,
                                        route=state.route,
                                        chat_history=history_str,
                                        summary=state.summary,
                                        current_query=state.query
                                        )

        logger.info(
            "Build prompt finished",
            extra={
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

        return {"final_context": final_context}

    async def generate_node(self, state: LeanAgentState) -> dict[str, str]:
        """Генерирует финальный ответ с учётом route, контекста и истории диалога."""
        started = time.perf_counter()
        answer = await self.llm_provider.generate(current_query=state.query,
                                                  data_prompt=state.final_context)


        logger.info(
            "Generate finished",
            extra={
                "route": state.route,
                "query": state.query,
                "answer_len": len(answer or ""),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

        return {"response_model": answer }

    @staticmethod
    def build_sources(retrieval_data: list[RetrieveItem]) -> list[dict[str, Any]]:
        """Общий маппинг RetrieveItem -> плоский dict источника для API-ответа.

        Используется и обычным /llm/answer (agent_routers.py), и SSE-веткой
        (событие 'sources' в run_stream) - раньше эта логика была продублирована
        прямо в agent_routers.py.
        """
        return [
            {
                "doc_id": item.metadata.doc_id,
                "parent_id": item.metadata.parent_id,
                "page_num": item.metadata.page_num,
                "score": item.metadata.score,
                "text": item.parent_chunk,
                "child_chunks": [c.text for c in item.child_chunks],
                "headers": item.metadata.headers,
                "source": item.metadata.source,
            }
            for item in retrieval_data
        ]

    async def run_stream(
        self,
        *,
        query: str,
        summary: str = "",
        history_messages_db: list[dict[str, str]],
    ):
        """SSE-вариант run(): стримит токены ответа вместо ожидания полного completion.

        Контракт событий: status -> (token|ping)* -> sources -> done. ping - пустой
        keep-alive между дельтами (см. PING_INTERVAL_S ниже), клиент его игнорирует.
        Компилированный
        self.app.ainvoke() не даёт стримить токены generate без отдельной машинерии
        LangGraph (astream_events) - узлы до generate штатно быстрые (роутинг/поиск),
        поэтому здесь они вызываются напрямую в том же порядке, что и в графе
        (см. _build_graph), а стримится только сам LLM-вызов в generate.
        """
        started = time.perf_counter()

        state = LeanAgentState(
            query=query,
            messages=history_messages_db or [],
            summary=summary,
            route="domain_rag",
            expanded_queries=[query],
        )

        state = state.model_copy(update=await self.route_node(state))
        yield {"event": "status", "data": {"stage": "route", "route": state.route}}

        if await self.decide_after_router(state) == "expand":
            state = state.model_copy(update=await self.expand_queries_node(state))
            yield {"event": "status", "data": {"stage": "expand"}}

            state = state.model_copy(update=await self.retrieve_multi_node(state))
            yield {"event": "status", "data": {"stage": "retrieve", "count": len(state.retrieval_data)}}

        state = state.model_copy(update=await self.build_prompt_node(state))

        # Пауза между дельтами от апстрим-LLM не ограничена сверху (медленная модель,
        # сетевые заминки у провайдера) - без heartbeat корпоративные proxy/firewall
        # перед nginx рвут "тихое" SSE-соединение по своему idle-таймауту (обычно 30-60с),
        # который мы не контролируем и не можем настроить снаружи. Событие "ping" не несёт
        # данных - фронт его игнорирует, но сам факт байтов в канале сбрасывает таймаут.
        PING_INTERVAL_S = 15.0
        answer_parts: list[str] = []
        token_iter = self.llm_provider.generate_stream(
            current_query=state.query, data_prompt=state.final_context
        ).__aiter__()
        while True:
            try:
                delta = await asyncio.wait_for(token_iter.__anext__(), timeout=PING_INTERVAL_S)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": {}}
                continue
            except StopAsyncIteration:
                break
            answer_parts.append(delta)
            yield {"event": "token", "data": {"text": delta}}

        answer = "".join(answer_parts)
        sources = self.build_sources(state.retrieval_data)
        yield {"event": "sources", "data": {"sources": sources}}
        yield {"event": "done", "data": {"answer": answer}}

        logger.info(
            "Lean agent run_stream finished",
            extra={
                "query": query,
                "route": state.route,
                "sources_count": len(sources),
                "answer_len": len(answer),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

    async def run(
        self,
        *,
        query: str,
        summary: str = "",
        history_messages_db: list[dict[str, str]]
    ) ->  dict[str, Any]:
        """Точка входа — собирает начальный стейт и запускает граф."""
        started = time.perf_counter()

        inputs = LeanAgentState(
            query=query,
            messages=history_messages_db or [],
            summary=summary,
            route="domain_rag",
            expanded_queries=[query],
        )

        final_state = await self.app.ainvoke(inputs)

        logger.info(
            "Lean agent run finished",
            extra={
                "query": query,
                "route": final_state.get("route"),
                "sources_count": len(final_state.get("sources", [])),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

        return final_state
