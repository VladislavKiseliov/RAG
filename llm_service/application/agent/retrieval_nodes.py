"""rerank_node/reflect_node/no_data_node - обработка результатов поиска."""

from __future__ import annotations

import time
from typing import Any

from llm_service.ai_config import get_live_config
from llm_service.application.agent.formatters import format_retrieval_item_for_prompt
from llm_service.application.lean_rag_models import LeanAgentState, PlanOutput, PlanSubtask, ReflectOutput, RetrieveItem
from llm_service.utils.logger_config import setup_logger

logger = setup_logger("llm_service.lean_rag_agent")

# Дефолтный текст no_data - честный отказ вместо LLM-галлюцинации на пустом/слабом
# контексте (Принцип №4 "Честность важнее умности", ARCHITECTURE.md §3).
_NO_DATA_ANSWER = "В базе знаний нет информации по вашему запросу."


class RetrievalNodesMixin:
    async def rerank_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНЫЙ rerank через TEI (bge-reranker-v2-m3, отдельный контейнер
        tei-reranker) - развёрнут 07.2026 как сознательное исключение из eval-ворот
        (ARCHITECTURE.md §1 п.3, второе исключение). Реранжирует по ЛУЧШЕМУ child-чанку
        каждого parent (то, что реально совпало с запросом при исходном векторном
        поиске - короткий точный фрагмент), не по parent_chunk целиком: тот может быть
        целой главой в тысячи символов - разбавляет сигнал кросс-энкодеру и рискует не
        влезть в его контекст. Сам parent_chunk (то, что уйдёт в промпт) не меняется -
        меняется только его новый score/позиция. Пустой retrieval_data - no-op, сетевой
        вызов не делается (RerankerService.rerank сам это обрабатывает).
        """
        if not state.retrieval_data:
            return {"retrieval_data": []}

        # Реранкер - кросс-энкодер без доступа к истории диалога, судит по буквальному
        # тексту query. Голый state.query может быть неполным вне контекста ("какие меры
        # применимы при нарушении" - нарушении чего?), а plan_node уже расшифровал вопрос
        # в конкретный поисковый запрос для retrieval - используем тот же текст и для
        # реранка, а не сырой исходный вопрос. Живой пример бага: один и тот же кусок
        # (акт приостановки ПНР) получал 0.004 против сырого запроса и 0.85 против
        # переписанного - реранкер и retrieval сравнивали с разными формулировками.
        rerank_query = state.query
        if state.plan and state.plan.subtasks:
            rerank_query = state.plan.subtasks[0].args.get("query", state.query)

        texts = [
            max(item.child_chunks, key=lambda c: c.score).text if item.child_chunks else item.parent_chunk
            for item in state.retrieval_data
        ]
        scored = await self.reranker_service.rerank(query=rerank_query, texts=texts)

        reordered: list[RetrieveItem] = []
        for entry in scored:
            original = state.retrieval_data[entry["index"]]
            new_metadata = original.metadata.model_copy(update={"score": entry["score"]})
            reordered.append(original.model_copy(update={"metadata": new_metadata}))
        return {"retrieval_data": reordered}

    async def reflect_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНЫЙ reflect - и grey_zone (слабый score), и empty (ничего не нашли) из
        decide_after_rerank теперь идут сюда, а не сразу в no_data (см. graph_builder.py).
        LLM смотрит на вопрос + то, что реально нашли (или "ничего"), и решает: хватает
        ли данных для ответа (sufficient), стоит ли поискать ещё другими формулировками
        (need_more + новые queries, которые execute_subtasks_node подхватит как новый
        state.plan), или вопрос в принципе не про эту базу (not_in_corpus).

        Максимум один круг уточнения (state.reflect_rounds) - на втором заходе не даём
        зацикливаться дальше, даже если LLM опять попросит "need_more": трактуем как
        sufficient (если хоть что-то нашли) или not_in_corpus (если так и пусто) -
        честный ответ лучше, чем бесконечный поиск."""
        if state.reflect_rounds >= 1:
            verdict = "sufficient" if state.retrieval_data else "not_in_corpus"
            return {"reflect_rounds": state.reflect_rounds + 1, "reflect_verdict": verdict}

        started = time.perf_counter()
        reflect_prompt = get_live_config().prompts.reflect_prompt
        found_content = "\n\n".join(
            format_retrieval_item_for_prompt(item) for item in state.retrieval_data
        ) or "(ничего не найдено)"
        prompt = reflect_prompt.format(query=state.query, found_content=found_content)

        result: ReflectOutput = await self.llm_gateway.generate_json(schema=ReflectOutput, prompt=prompt)

        verdict = result.verdict
        update: dict[str, Any] = {"reflect_rounds": state.reflect_rounds + 1}

        if verdict == "need_more" and result.new_queries:
            max_subtasks = get_live_config().gateway.max_subtasks
            queries = result.new_queries[:max_subtasks]
            update["plan"] = PlanOutput(
                subtasks=[
                    PlanSubtask(tool="search_docs", args={"query": q, "doc_filter": None}) for q in queries
                ],
                synthesis=f"reflect: уточняющий поиск ({len(queries)} запрос(ов))",
            )
        elif verdict == "need_more":
            # LLM попросила уточнение, но не дала новых формулировок - искать больше
            # нечем, трактуем как то, что реально есть.
            verdict = "sufficient" if state.retrieval_data else "not_in_corpus"

        update["reflect_verdict"] = verdict

        logger.info(
            "Reflect finished",
            extra={
                "query": state.query,
                "verdict": verdict,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return update

    async def no_data_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНАЯ терминальная нода, достижима с сегодняшнего дня (см. decide_after_rerank) -
        честный отказ вместо LLM-галлюцинации на пустом/слабом контексте (Принцип №4)."""
        return {"retrieval_empty": True, "response_model": _NO_DATA_ANSWER}
