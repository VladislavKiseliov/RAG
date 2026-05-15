from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph


from llm_service.LLM_provider import OpenAICompatLLMProvider
from llm_service.application.lean_rag_models import LeanAgentState, QueryRouterProtocol, RetrievalResult, \
    FinalPromptData, RetrieveItem
from llm_service.application.services.query_service import QueryExpansionService
from llm_service.application.services.retrieval_service import  RetrievalService
from llm_service.promt.promts import QUERY_EXPANSION_PROMPT
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
        route = self.query_router.route(state.query)

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
        print(f"{state.query=}")
        print(f"{state.messages=}")
        raw_expansion = (await self.llm_provider.generate_general(query=QUERY_EXPANSION_PROMPT.format(summary= state.summary,
                                                                                                      recent_history = state.messages,
                                                                                                      query = state.query),
                                                                  context="")).strip()
        print(f"{raw_expansion=}")
        expanded_pack = await QueryExpansionService.expand(original_query=state.query,
                                                           row_query=raw_expansion)
        print(f"{expanded_pack=}")
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


    def _format_child_chunks_retrive_data(self,item:RetrieveItem) -> str:
        children = ", ".join(f"Чанк:{child.text} - score {child.score*100:.0f}%"
                             for child in item.child_chunks)


        return f"Раздел {item.metadata.headers}:{item.parent_chunk}\n({children})"



    async def build_prompt_node(self, state: LeanAgentState) -> dict[str, Any]:
        started = time.perf_counter()

        context_str = "\n\n".join((self._format_child_chunks_retrive_data(item) for item in state.retrieval_data))
        history_str = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in state.messages
        )

        final_context = FinalPromptData(context=context_str,
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
