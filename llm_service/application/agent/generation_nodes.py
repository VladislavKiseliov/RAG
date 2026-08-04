"""build_prompt_node/generate_node/extract_sources_node/post_actions_node -
сборка промпта, вызов LLM, постобработка ответа."""

from __future__ import annotations

import time
from typing import Any

from llm_service.application.agent.formatters import build_sources_payload, format_retrieval_item_for_prompt
from llm_service.application.lean_rag_models import FinalPromptData, LeanAgentState
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.lean_rag_agent")


class GenerationNodesMixin:
    async def build_prompt_node(self, state: LeanAgentState) -> dict[str, Any]:
        started = time.perf_counter()

        context_str = "\n\n".join(format_retrieval_item_for_prompt(item) for item in state.retrieval_data)
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

    async def extract_sources_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНАЯ нода: тот же build_sources_payload, что раньше вызывался инлайново в
        run_stream()/agent_routers.py - вынесен в ноду графа, поведение не меняется."""
        return {"sources": build_sources_payload(state.retrieval_data)}

    async def post_actions_node(self, state: LeanAgentState) -> dict[str, Any]:
        """ЗАГЛУШКА: настоящий no-op - не делает I/O, не вызывает LLM, proposed_action
        остаётся None. Нет ни промпта, ни write-инструментов с реальной реализацией
        (create_task/create_note/update_note - все NotImplementedError в реестре)."""
        return {"proposed_action": None}
