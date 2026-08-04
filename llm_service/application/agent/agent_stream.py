"""SSE-стриминг вручную дублирует переходы графа (см. graph_builder.py) - LangGraph
не даёт стримить токены generate без отдельной машинерии (astream_events), а узлы
до generate штатно быстрые (планирование/поиск), так что дублирование императивным
кодом дешевле, чем тащить astream_events ради одного узла."""

from __future__ import annotations

import time
from typing import Any, AsyncIterator

from llm_service.LLM_provider import OpenAICompatLLMProvider
from llm_service.application.agent import routing_decisions as decisions
from llm_service.application.agent.agent_nodes import AgentNodes
from llm_service.application.lean_rag_models import LeanAgentState
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.lean_rag_agent")


class StreamRunner:
    """Контракт событий: status -> token* -> sources -> done. Keep-alive между
    дельтами - забота EventSourceResponse (см. agent_routers.py), сам генератор
    ничего не пингует.

    ВРЕМЕННО (см. graph_builder.py): ML-роутер отключён, planner-first схема - те
    же узлы и тот же порядок, что и в скомпилированном графе, вручную, ради
    стриминга.

    Ретраи/heartbeat/fallback (см. run()) защищают ТОЛЬКО сам вызов LLM -
    осознанно, не plan_node/execute_subtasks_node/build_prompt_node. Это
    внутренние, обычно быстрые вызовы (Qdrant в той же docker-сети) - не тот класс
    ненадёжности, что внешний HTTP до стороннего шлюза, ради которого строилась
    вся защита ниже. Сбой в них сразу уходит в общий except в
    agent_routers.py::answer_question_stream как обычная ошибка, без ретрая.
    """

    def __init__(self, *, nodes: AgentNodes, llm_provider: OpenAICompatLLMProvider) -> None:
        self._nodes = nodes
        self._llm_provider = llm_provider

    async def run(
        self,
        *,
        query: str,
        summary: str = "",
        history_messages_db: list[dict[str, str]],
    ) -> AsyncIterator[dict[str, Any]]:
        started = time.perf_counter()

        state = LeanAgentState(
            query=query,
            messages=history_messages_db or [],
            summary=summary,
            route="domain_rag",
            expanded_queries=[query],
        )

        state = state.model_copy(update=await self._nodes.plan_node(state))
        yield {"event": "status", "data": {"stage": "plan", "subtasks_count": len(state.plan.subtasks) if state.plan else 0}}

        state = state.model_copy(update=await self._nodes.execute_subtasks_node(state))
        execute_decision = await decisions.decide_after_execute_subtasks(state)
        yield {"event": "status", "data": {"stage": "retrieve", "count": len(state.retrieval_data)}}

        if execute_decision == "rerank":
            # rerank_node - реальный (развёрнут 07.2026, см. её docstring). decide_after_rerank
            # обязателен здесь же - иначе /llm/answer (граф, через no_data-ветку) и
            # /llm/answer/stream (этот метод) разошлись бы: граф корректно обрывается в
            # no_data при пустом/слабом retrieval, а этот метод раньше безусловно шёл в
            # generate дальше.
            #
            # Цикл (не просто if) - зеркалит edge графа reflect -(need_more)-> execute_subtasks
            # -> rerank -> ...: если reflect попросил уточняющий поиск, execute_subtasks_node
            # подхватывает новый state.plan (его туда кладёт reflect_node) и мы реранкаем заново.
            # decide_after_execute_subtasks после повторного поиска не перепроверяем - reflect_node
            # всегда кладёт search_docs-подзадачи в "need_more", так что итог детерминирован ("rerank").
            # Само зацикливание ограничено одним кругом внутри reflect_node (см. её докстринг).
            while True:
                state = state.model_copy(update=await self._nodes.rerank_node(state))
                rerank_decision = await decisions.decide_after_rerank(state)

                if rerank_decision in ("grey_zone", "empty"):
                    state = state.model_copy(update=await self._nodes.reflect_node(state))
                    reflect_decision = await decisions.decide_after_reflect(state)

                    if reflect_decision == "need_more":
                        state = state.model_copy(update=await self._nodes.execute_subtasks_node(state))
                        yield {"event": "status", "data": {"stage": "retrieve", "count": len(state.retrieval_data)}}
                        continue

                    rerank_decision = "sufficient" if reflect_decision == "sufficient" else "empty"

                break

            if rerank_decision == "empty":
                state = state.model_copy(update=await self._nodes.no_data_node(state))
                state = state.model_copy(update=await self._nodes.extract_sources_node(state))
                yield {"event": "token", "data": {"text": state.response_model}}
                yield {"event": "sources", "data": {"sources": state.sources}}
                yield {"event": "done", "data": {"answer": state.response_model}}
                logger.info(
                    "Lean agent run_stream finished (no_data)",
                    extra={
                        "query": query,
                        "route": state.route,
                        "duration_ms": int((time.perf_counter() - started) * 1000),
                    },
                )
                return

        state = state.model_copy(update=await self._nodes.build_prompt_node(state))

        answer_parts: list[str] = []
        try:
            async for delta in self._llm_provider.generate_stream(
                current_query=state.query, data_prompt=state.final_context
            ):
                answer_parts.append(delta)
                yield {"event": "token", "data": {"text": delta}}
        except Exception as exc:
            if answer_parts:
                logger.warning("LLM stream interrupted mid-generation: %s", exc)
                note = "\n\n_[ответ прерван: обрыв соединения с LLM]_"
                answer_parts.append(note)
                yield {"event": "token", "data": {"text": note}}
            else:
                logger.warning(
                    "LLM stream produced zero tokens, falling back to non-streaming generate(): %s", exc,
                )
                try:
                    answer = await self._llm_provider.generate(
                        current_query=state.query, data_prompt=state.final_context
                    )
                except Exception as fallback_exc:
                    logger.exception("Non-streaming fallback also failed")
                    note = f"_Не удалось получить ответ: {fallback_exc}_"
                    answer_parts.append(note)
                    yield {"event": "token", "data": {"text": note}}
                else:
                    answer_parts.append(answer)
                    yield {"event": "token", "data": {"text": answer}}

        answer = "".join(answer_parts)
        state = state.model_copy(update=await self._nodes.extract_sources_node(state))
        sources = state.sources

        state = state.model_copy(update={"response_model": answer})
        if await decisions.decide_after_generate(state) == "post_actions":
            await self._nodes.post_actions_node(state)

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
