"""LeanRagAgent - тонкий фасад точки входа. Вся логика разнесена по
llm_service/application/agent/ (SRP): agent_nodes.py - бизнес-логика нод,
routing_decisions.py - гейты, graph_builder.py - сборка LangGraph,
formatters.py - форматирование данных. run()/run_stream() - оба через один и тот
же скомпилированный граф self.app (см. run_stream)."""

from __future__ import annotations

import time
from typing import Any, AsyncIterator

from llm_service.LLM_provider import OpenAICompatLLMProvider
from llm_service.application.agent.agent_nodes import AgentNodes
from llm_service.application.agent.formatters import build_sources_payload
from llm_service.application.agent.graph_builder import build_agent_graph
from llm_service.application.lean_rag_models import LeanAgentState, RetrieveItem
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
        retrieval_service: RetrievalService,
        reranker_service: RerankerService,
    ) -> None:
        self.llm_provider = llm_provider
        self.retrieval_service = retrieval_service
        self.reranker_service = reranker_service
        self.tool_registry = build_tool_registry(retrieval_service=retrieval_service)
        self.llm_gateway = LLMGateway(llm_provider=llm_provider)

        self.nodes = AgentNodes(
            llm_provider=llm_provider,
            llm_gateway=self.llm_gateway,
            retrieval_service=retrieval_service,
            reranker_service=reranker_service,
            tool_registry=self.tool_registry,
        )
        self.app = build_agent_graph(self.nodes)

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

    async def run_stream(
        self,
        *,
        query: str,
        summary: str = "",
        history_messages_db: list[dict[str, str]],
    ) -> AsyncIterator[dict[str, Any]]:
        """SSE-вариант run(): стримит токены ответа вместо ожидания полного completion,
        через ТОТ ЖЕ скомпилированный граф self.app, что и run() (не отдельная копия
        нод/переходов, как было раньше в agent_stream.py::StreamRunner - удалён).

        LangGraph astream_events() здесь не подходит: on_chat_model_stream всплывает
        только из LangChain Runnable/BaseChatModel, а LLM-вызов (LLM_provider.py)
        сделан на сыром openai SDK ради собственной ретрай/TTFT-логики
        (_stream_completion_with_retry) - от него в astream_events() не пришло бы
        вообще ничего. Вместо этого - custom stream_mode: ноды, которым есть что
        стримить (plan_node/execute_subtasks_node - "status", generate_node/
        no_data_node - "token", см. их докстринги), пишут через
        get_stream_writer()/get_safe_stream_writer() напрямую, эти события уходят
        через "custom"-канал astream() ниже. "values"-канал в той же подписке даёт
        полный снэпшот state после каждой ноды - последний из них (после END) несёт
        финальные response_model/retrieval_data, которые sources/done ниже читают
        так же, как /llm/answer читает final_state после ainvoke() (agent_routers.py)."""
        started = time.perf_counter()

        inputs = LeanAgentState(
            query=query,
            messages=history_messages_db or [],
            summary=summary,
            route="domain_rag",
        )

        final_state: dict[str, Any] = {}
        async for mode, chunk in self.app.astream(inputs, stream_mode=["custom", "values"]):
            if mode == "custom":
                yield chunk
            else:
                final_state = chunk

        answer = final_state.get("response_model", "")
        sources = self.build_sources(final_state.get("retrieval_data", []))
        degraded = final_state.get("response_degraded", False)

        yield {"event": "sources", "data": {"sources": sources}}
        yield {"event": "done", "data": {"answer": answer, "degraded": degraded}}

        logger.info(
            "Lean agent run_stream finished",
            extra={
                "query": query,
                "route": final_state.get("route"),
                "sources_count": len(sources),
                "answer_len": len(answer or ""),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )

    @staticmethod
    def build_sources(retrieval_data: list[RetrieveItem]) -> list[dict[str, Any]]:
        """Используется и обычным /llm/answer (agent_routers.py), и SSE-веткой."""
        return build_sources_payload(retrieval_data)
