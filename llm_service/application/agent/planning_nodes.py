"""plan_node/execute_subtasks_node - реальный planner-first вход графа (см.
graph_builder.py) и диспетчер тулов."""

from __future__ import annotations

import time
from typing import Any

from prometheus_client import Counter

from llm_service.ai_config import get_live_config
from llm_service.application.agent.formatters import format_chat_history, merge_appendix_result, merge_search_docs_results
from llm_service.application.agent.retrieval_nodes import _MAX_APPENDIX_CONTEXT_CHARS
from llm_service.application.lean_rag_models import LeanAgentState, PlanOutput, PlanSubtask, RetrieveItem
from llm_service.utils.logger_config import setup_logger
from llm_service.utils.stream_writer import get_safe_stream_writer

logger = setup_logger("llm_service.lean_rag_agent")

# plan_node - точка входа 100% живого трафика (см. её докстринг) - частота этого
# счётчика прямой индикатор здоровья JSON-контракта плана и дешёвой модели.
PLAN_FALLBACK_COUNT = Counter(
    "llm_plan_fallback_total",
    "plan_node fell back to a default search_docs(query) plan after an LLM/JSON contract failure",
)


class PlanningNodesMixin:
    async def plan_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНЫЙ планировщик - точка входа графа вместо ML-роутера (временное
        решение, см. ISSUES.md/ARCHITECTURE.md: роутер отключён от графа, не удалён,
        чтобы можно было легко вернуть). Смотрит на историю диалога и текущий вопрос,
        через LLM решает, нужен ли поиск по базе и какими формулировками - вплоть до
        пустого плана для smalltalk/оффтопика (тогда decide_after_execute_subtasks
        уйдёт сразу в build_prompt, без похода в Qdrant).

        plan_node - точка входа, через которую проходит 100% трафика (включая
        светскую беседу, которая вообще не требовала бы LLM) - в отличие от
        generate_node ниже по графу (ретраи/TTFT/фолбэк на нестримящий вызов) сбой
        JSON-контракта здесь раньше означал голый 500 даже на "привет". Деградируем
        до дефолтного плана - обычный search_docs по сырому вопросу пользователя,
        почти всегда осмысленная реакция на невалидный JSON/таймаут/5xx апстрима -
        вместо того, чтобы ронять весь ответ. PLAN_FALLBACK_COUNT - частота этого
        события, прямой индикатор здоровья JSON-контракта и качества дешёвой модели."""
        started = time.perf_counter()
        plan_prompt = get_live_config().prompts.plan_prompt
        recent_history_str = format_chat_history(state.messages)
        prompt = plan_prompt.format(summary=state.summary, recent_history=recent_history_str, query=state.query)

        try:
            plan = await self.llm_gateway.generate_json(schema=PlanOutput, prompt=prompt)
        except Exception:
            PLAN_FALLBACK_COUNT.inc()
            logger.exception(
                "plan_node: LLM/JSON contract failed, falling back to default search plan",
                extra={"event": "plan_fallback_used", "query": state.query},
            )
            plan = PlanOutput(
                subtasks=[PlanSubtask(tool="search_docs", args={"queries": [state.query], "doc_filter": None})],
                synthesis="plan_fallback_used",
            )

        max_subtasks = get_live_config().gateway.max_subtasks
        if len(plan.subtasks) > max_subtasks:
            plan = plan.model_copy(update={"subtasks": plan.subtasks[:max_subtasks]})

        # route отражает решение plan (нужен ли поиск), а не ML-роутер (отключён от
        # графа, см. legacy_disabled_nodes.py) - без этого build_prompt_node/generate_node
        # всегда получали бы захардкоженный "domain_rag" и никогда не выбирали бы
        # system_prompt_chat, даже для пустого плана (светская беседа/мета-вопрос про
        # сам диалог). "smalltalk" здесь - технический ярлык для "поиск не нужен", не
        # обязательно буквально приветствие.
        route = "smalltalk" if not plan.subtasks else "domain_rag"

        # SSE "status"-событие (см. lean_rag_agent.py::run_stream, custom stream_mode) -
        # no-op вне графа/вне astream(stream_mode="custom") (get_safe_stream_writer).
        get_safe_stream_writer()({"event": "status", "data": {"stage": "plan", "subtasks_count": len(plan.subtasks)}})

        logger.info(
            "Plan finished",
            extra={
                "query": state.query,
                "subtasks_count": len(plan.subtasks),
                "route": route,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return {"plan": plan, "route": route}

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

        # Накопление между кругами (reflect need_more -> сюда же снова, см.
        # retrieval_nodes.py::reflect_node): раньше retrieval_data перезаписывался
        # целиком результатами только текущего круга - агент терял то, что нашёл на
        # предыдущем круге, даже если это было релевантно, просто под другой
        # формулировкой ("искал так - нашёл это, искал иначе - нашёл то" должно
        # складываться, а не подменяться). Мёржим свежие находки с уже накопленным
        # state.retrieval_data, дедуп по parent_id (глобально уникальный PK), оставляем
        # версию с большим score - тот же принцип, что merge_search_docs_results уже
        # применяет внутри одного круга. Объединённый пул уходит дальше в rerank
        # (decide_after_execute_subtasks), который единообразно пересчитает score для
        # всех элементов сразу против актуальной формулировки - "выбрать лучшее из
        # всего", а не только из последнего круга.
        new_items = merge_search_docs_results(results)
        merged: dict[str, RetrieveItem] = {item.metadata.parent_id: item for item in state.retrieval_data}
        for item in new_items:
            existing = merged.get(item.metadata.parent_id)
            if existing is None or item.metadata.score > existing.metadata.score:
                merged[item.metadata.parent_id] = item
        retrieval_data = sorted(merged.values(), key=lambda item: item.metadata.score, reverse=True)

        update: dict[str, Any] = {"subtask_results": results, "retrieval_data": retrieval_data}
        # get_appendix (в отличие от search_docs) не идёт в retrieval_data - это сырой
        # текст приложения, не оценённый rerank'ом чанк. Пишем только если реально что-то
        # нашли: пустой/отсутствующий результат не должен затирать appendix_context,
        # который мог быть выставлен на предыдущем круге (reflect/build_prompt code-gate).
        appendix_text = merge_appendix_result(results)
        if appendix_text:
            update["appendix_context"] = appendix_text[:_MAX_APPENDIX_CONTEXT_CHARS]

        # Эта нода может исполниться дважды за прогон (reflect need_more -> сюда же
        # снова) - статус уходит на каждый реальный вызов, не только на первый.
        get_safe_stream_writer()({"event": "status", "data": {"stage": "retrieve", "count": len(update["retrieval_data"])}})

        return update
