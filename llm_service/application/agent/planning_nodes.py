"""plan_node/execute_subtasks_node - реальный planner-first вход графа (см.
graph_builder.py) и диспетчер тулов."""

from __future__ import annotations

import time
from typing import Any

from llm_service.ai_config import get_live_config
from llm_service.application.agent.formatters import merge_search_docs_results
from llm_service.application.lean_rag_models import LeanAgentState, PlanOutput
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.lean_rag_agent")


class PlanningNodesMixin:
    async def plan_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНЫЙ планировщик - точка входа графа вместо ML-роутера (временное
        решение, см. ISSUES.md/ARCHITECTURE.md: роутер отключён от графа, не удалён,
        чтобы можно было легко вернуть). Смотрит на историю диалога и текущий вопрос,
        через LLM решает, нужен ли поиск по базе и какими формулировками - вплоть до
        пустого плана для smalltalk/оффтопика (тогда decide_after_execute_subtasks
        уйдёт сразу в build_prompt, без похода в Qdrant). Не оборачиваем LLM-вызов в
        try/except - тот же принцип, что и у expand_queries_node: сбой уходит в общий
        except в agent_routers.py, без тихого фолбэка (см. docstring StreamRunner)."""
        started = time.perf_counter()
        plan_prompt = get_live_config().prompts.plan_prompt
        recent_history_str = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in state.messages
        )
        prompt = plan_prompt.format(summary=state.summary, recent_history=recent_history_str, query=state.query)

        plan = await self.llm_gateway.generate_json(schema=PlanOutput, prompt=prompt)

        max_subtasks = get_live_config().gateway.max_subtasks
        if len(plan.subtasks) > max_subtasks:
            plan = plan.model_copy(update={"subtasks": plan.subtasks[:max_subtasks]})

        logger.info(
            "Plan finished",
            extra={
                "query": state.query,
                "subtasks_count": len(plan.subtasks),
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return {"plan": plan}

    async def execute_subtasks_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНЫЙ универсальный диспетчер реестра (ARCHITECTURE.md §3/§8):
        находит tool по имени, валидирует args по args_schema, вызывает fn.
        Защитно отклоняет любой tool с access != "read", даже если plan ошибочно его
        предложит - вторая линия защиты сверх системного промпта plan. С тех пор как
        plan_node стал реальным (не заглушка), этот узел получает 100% живого
        трафика - большинство tool_registry.py тулов, кроме search_docs, всё ещё
        NotImplementedError-заглушки (промпт plan_node просит модель не предлагать
        их, но это не гарантия, а вероятностное поведение LLM) - оборачиваем вызов
        каждой подзадачи отдельно, чтобы одна плохая подзадача не роняла весь ответ."""
        results: list[dict[str, Any]] = []
        subtasks = state.plan.subtasks if state.plan else []
        for subtask in subtasks:
            tool = self.tool_registry.get(subtask.tool)
            if tool is None:
                logger.warning("execute_subtasks: unknown tool '%s', skipping", subtask.tool)
                continue
            if tool.access != "read":
                logger.warning(
                    "execute_subtasks: refusing to auto-execute write tool '%s' - write only via post_actions",
                    subtask.tool,
                )
                continue
            try:
                args = tool.args_schema.model_validate(subtask.args)
                result = await tool.fn(**args.model_dump())
            except Exception:
                logger.exception("execute_subtasks: tool '%s' failed, skipping subtask", subtask.tool)
                continue
            results.append({"tool": subtask.tool, "result": result})
        return {"subtask_results": results, "retrieval_data": merge_search_docs_results(results)}
