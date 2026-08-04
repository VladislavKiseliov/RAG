"""LeanRagAgent - тонкий фасад точки входа. Вся логика разнесена по
llm_service/application/agent/ (SRP): agent_nodes.py - бизнес-логика нод,
routing_decisions.py - гейты, graph_builder.py - сборка LangGraph,
agent_stream.py - SSE-стриминг, formatters.py - форматирование данных."""

from __future__ import annotations

import time
from typing import Any, AsyncIterator

from llm_service.LLM_provider import OpenAICompatLLMProvider
from llm_service.application.agent.agent_nodes import AgentNodes
from llm_service.application.agent.agent_stream import StreamRunner
from llm_service.application.agent.formatters import build_sources_payload
from llm_service.application.agent.graph_builder import build_agent_graph
from llm_service.application.lean_rag_models import LeanAgentState, QueryRouterProtocol, RetrieveItem
from llm_service.application.services.reranker_service import RerankerService
from llm_service.application.services.retrieval_service import RetrievalService
from llm_service.llm_gateway import LLMGateway
from llm_service.tool_registry import build_tool_registry
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.lean_rag_agent")


class LeanRagAgent:
    def __init__(
        self,
        *,
        llm_provider: OpenAICompatLLMProvider,
        query_router: QueryRouterProtocol,
        retrieval_service: RetrievalService,
        reranker_service: RerankerService,
    ) -> None:
        self.llm_provider = llm_provider
        self.query_router = query_router
        self.retrieval_service = retrieval_service
        self.reranker_service = reranker_service
        self.tool_registry = build_tool_registry(retrieval_service=retrieval_service)
        self.llm_gateway = LLMGateway(llm_provider=llm_provider)

        self.nodes = AgentNodes(
            llm_provider=llm_provider,
            llm_gateway=self.llm_gateway,
            query_router=query_router,
            retrieval_service=retrieval_service,
            reranker_service=reranker_service,
            tool_registry=self.tool_registry,
        )
        self.app = build_agent_graph(self.nodes)
        self._stream_runner = StreamRunner(nodes=self.nodes, llm_provider=llm_provider)

        logger.info("Lean RAG agent initialized",)

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

    def run_stream(
        self,
        *,
        query: str,
        summary: str = "",
        history_messages_db: list[dict[str, str]],
    ) -> AsyncIterator[dict[str, Any]]:
        """SSE-вариант run(): стримит токены ответа вместо ожидания полного completion.
        Делегирует в StreamRunner (agent_stream.py) - см. его докстринг про контракт
        событий и почему граф дублируется императивным кодом."""
        return self._stream_runner.run(
            query=query, summary=summary, history_messages_db=history_messages_db
        )

    @staticmethod
    def build_sources(retrieval_data: list[RetrieveItem]) -> list[dict[str, Any]]:
        """Используется и обычным /llm/answer (agent_routers.py), и SSE-веткой."""
        return build_sources_payload(retrieval_data)
