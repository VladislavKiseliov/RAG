"""rerank_node/reflect_node/no_data_node - обработка результатов поиска."""

from __future__ import annotations

import time
from typing import Any

from prometheus_client import Counter

from llm_service.ai_config import get_live_config
from llm_service.application.agent.formatters import format_retrieval_item_for_prompt
from llm_service.application.lean_rag_models import LeanAgentState, PlanOutput, PlanSubtask, ReflectOutput, RetrieveItem
from llm_service.utils.logger_config import setup_logger
from llm_service.utils.stream_writer import get_safe_stream_writer

logger = setup_logger("llm_service.lean_rag_agent")

# Дефолтный текст no_data - честный отказ вместо LLM-галлюцинации на пустом/слабом
# контексте (Принцип №4 "Честность важнее умности", ARCHITECTURE.md §3).
_NO_DATA_ANSWER = "В базе знаний нет информации по вашему запросу."

# Симметрично PLAN_FALLBACK_COUNT (planning_nodes.py) - частота деградации на этом
# пути отдельно важна: reflect достижим только когда что-то уже слабо нашлось.
REFLECT_FALLBACK_COUNT = Counter(
    "llm_reflect_fallback_total",
    "reflect_node fell back to a verdict derived from retrieval_data alone after an LLM/JSON contract failure",
)

# Приложение может занимать несколько страниц - это сырой текст, не чанк с рассчитанным
# скором (см. A21 в rag_service/ISSUES.md), в промпт целиком не льём.
_MAX_APPENDIX_CONTEXT_CHARS = 6000


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
        # Обновлено 2026-08-06: берём АКТУАЛЬНУЮ формулировку (последнюю), не склеиваем
        # все через пробел - bge-reranker-v2-m3 обучен на парах "один запрос - один
        # пассаж", склейка нескольких перефразировок в одну строку - данные вне
        # распределения обучения, разбавляет сигнал так же, как разбавлял бы целый
        # parent_chunk вместо лучшего child (та же причина, что и там). Если reflect
        # переформулировал (state.plan заменён целиком на новый) - реранкаем по новой
        # формулировке, не по смеси со старой. get_appendix - второй тул (args:
        # {"document_code"}, без "queries") - пропускаем его подзадачи тем же фильтром
        # по ключу, чтобы план вида [get_appendix, search_docs] не откатывал rerank_query
        # на сырой state.query.
        query_parts = [
            q for subtask in state.plan.subtasks if "queries" in subtask.args for q in subtask.args["queries"]
        ] if state.plan else []
        rerank_query = query_parts[-1] if query_parts else state.query

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

        # Срез после реранка (обновлено 2026-08-06) - кросс-энкодер до этого места
        # только пересортировывал, весь пул (включая слабый хвост) доезжал до
        # generate_node. После накопления между кругами reflect пул может удвоиться -
        # без среза это чистое ухудшение (больше слабого контекста - больше материала
        # для "додумывания", см. §6.9 AGENT_GRAPH_CURRENT.md). Режем здесь, не в
        # build_prompt_node - extract_sources_node тоже читает retrieval_data, источники
        # на фронте должны соответствовать тому, что реально видела LLM.
        final_k = get_live_config().gateway.rerank_final_k
        return {"retrieval_data": reordered[:final_k]}

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
        # reflect раньше видел только НАЙДЕННОЕ, не то, КАКИМИ ЗАПРОСАМИ искали - не мог
        # отличить "первая попытка не сработала, надо честно другой заход" от "первая
        # формулировка была почти правильной, дожать бы синонимом" - в обоих случаях
        # получал одну и ту же картину и мог предложить new_queries, близкие по смыслу к
        # уже пробованным (тот же провал заново). Скор - общий по всем найденным
        # фрагментам круга, не по отдельным queries (rerank_node скорит чанки, не
        # исходные формулировки, которые их нашли).
        tried_queries_list = [
            q for subtask in state.plan.subtasks if "queries" in subtask.args for q in subtask.args["queries"]
        ] if state.plan else []
        if tried_queries_list:
            top_score = state.retrieval_data[0].metadata.score if state.retrieval_data else 0.0
            tried_queries = (
                "\n".join(f'- "{q}"' for q in tried_queries_list)
                + f"\nЛучший итоговый скор релевантности среди всего найденного этими запросами: {top_score:.2f}"
            )
        else:
            tried_queries = "(поиск ещё не выполнялся)"
        prompt = reflect_prompt.format(query=state.query, found_content=found_content, tried_queries=tried_queries)

        # Асимметрия с plan_node (у того есть фолбэк, здесь не было): generate_json
        # делает один ретрай на невалидном JSON - если и он не пройдёт, исключение
        # раньше улетало наружу необработанным в общий except агента (502), причём в
        # худший момент - reflect достижим только на grey_zone/empty (что-то уже
        # нашлось, но слабо), то есть пользователь получал ошибку вместо честного
        # ответа с тем, что реально есть. Тот же паттерн деградации, что у plan_node.
        try:
            result: ReflectOutput = await self.llm_gateway.generate_json(schema=ReflectOutput, prompt=prompt)
        except Exception:
            REFLECT_FALLBACK_COUNT.inc()
            logger.exception(
                "reflect_node: LLM/JSON contract failed, falling back to verdict from retrieval_data alone",
                extra={"event": "reflect_fallback_used", "query": state.query},
            )
            verdict = "sufficient" if state.retrieval_data else "not_in_corpus"
            return {"reflect_rounds": state.reflect_rounds + 1, "reflect_verdict": verdict}

        verdict = result.verdict
        update: dict[str, Any] = {"reflect_rounds": state.reflect_rounds + 1}

        if verdict == "need_more" and result.new_queries:
            max_subtasks = get_live_config().gateway.max_subtasks
            queries = result.new_queries[:max_subtasks]
            update["plan"] = PlanOutput(
                subtasks=[PlanSubtask(tool="search_docs", args={"queries": queries, "doc_filter": None})],
                synthesis=f"reflect: уточняющий поиск ({len(queries)} запрос(ов))",
            )
        elif verdict == "need_more":
            # LLM попросила уточнение, но не дала новых формулировок - искать больше
            # нечем, трактуем как то, что реально есть.
            verdict = "sufficient" if state.retrieval_data else "not_in_corpus"

        update["reflect_verdict"] = verdict

        # needs_appendix - независимый от verdict сигнал (см. reflect_prompt): LLM видит
        # запрос+найденное, но не UUID документов (format_retrieval_item_for_prompt
        # показывает только filename) - поэтому LLM решает ТОЛЬКО "нужен ли текст
        # приложения", а какой doc_id запрашивать, код резолвит сам из уже найденного
        # топ-результата, не полагаясь на то, что LLM мог бы придумать/перепутать UUID.
        if result.needs_appendix and state.retrieval_data:
            doc_id = state.retrieval_data[0].metadata.doc_id
            appendix_text = await self.retrieval_service.get_appendix(doc_id)
            if appendix_text:
                update["appendix_context"] = appendix_text[:_MAX_APPENDIX_CONTEXT_CHARS]

        logger.info(
            "Reflect finished",
            extra={
                "query": state.query,
                "verdict": verdict,
                "needs_appendix": result.needs_appendix,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        return update

    async def no_data_node(self, state: LeanAgentState) -> dict[str, Any]:
        """РЕАЛЬНАЯ терминальная нода, достижима с сегодняшнего дня (см. decide_after_rerank) -
        честный отказ вместо LLM-галлюцинации на пустом/слабом контексте (Принцип №4).

        Очищает retrieval_data: `not_in_corpus` от reflect_node достижим и при непустом
        (просто слабом/нерелевантном) retrieval_data - без очистки extract_sources_node
        строил бы список источников рядом с текстом "в базе знаний нет информации",
        что читается как противоречие (раз есть источники, почему нет информации).

        Граф идёт отсюда прямо в END, минуя generate_node (см. graph_builder.py) -
        значит для SSE (lean_rag_agent.py::run_stream) это единственное место, которое
        может доставить текст ответа как "token"-событие на этом пути; фронт
        (useAiChat.js) рендерит сообщение только по token-событиям, "done".answer не
        читает вообще."""
        get_safe_stream_writer()({"event": "token", "data": {"text": _NO_DATA_ANSWER}})
        return {"retrieval_empty": True, "response_model": _NO_DATA_ANSWER, "retrieval_data": []}
