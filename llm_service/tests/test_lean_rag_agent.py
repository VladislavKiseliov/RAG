from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_service.application.lean_rag_agent import LeanRagAgent
from llm_service.application.agent import formatters
from llm_service.application.agent import planning_nodes
from llm_service.application.agent import routing_decisions as decisions
from llm_service.application.lean_rag_models import (
    ChildChunk,
    FinalPromptData,
    LeanAgentState,
    PlanOutput,
    PlanSubtask,
    RetrievalResult,
    RetrieveItem,
    RetrieveItemMetadata,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_PLAN_RESPONSE = (
    '{"subtasks": [{"tool": "search_docs", "args": {"queries": ["search query"], "doc_filter": null}}], '
    '"synthesis": ""}'
)
_EMPTY_PLAN_RESPONSE = '{"subtasks": [], "synthesis": "smalltalk, поиск не нужен"}'
# Дефолт для reflect - not_in_corpus (не need_more): изолированные тесты, которые не
# про reflect как таковой, не должны внезапно зацикливаться на дополнительный поиск -
# тот же результат (no_data), что был бы без reflect вообще.
_DEFAULT_REFLECT_RESPONSE = '{"verdict": "not_in_corpus", "new_queries": []}'
# Уникальная фраза из reflect_prompt (ai_config.toml) - по ней различаем, что за
# generate_json_raw-вызов пришёл: от plan_node или от reflect_node. Оба читают один и
# тот же llm_provider.generate_json_raw (через llm_gateway.generate_json).
_REFLECT_PROMPT_MARKER = "оцениваешь, достаточно ли найденных фрагментов"


def make_agent(
    llm_answer: str = "финальный ответ",
    plan_response: str = _DEFAULT_PLAN_RESPONSE,
    reflect_response: str = _DEFAULT_REFLECT_RESPONSE,
    retrieval_items: list[RetrieveItem] | None = None,
    reranker_side_effect=None,
) -> LeanRagAgent:
    """plan_response/reflect_response - сырые ответы generate_json_raw для plan_node и
    reflect_node соответственно (оба вызывают один и тот же llm_provider.generate_json_raw
    через llm_gateway.generate_json, различаем по маркеру в тексте промпта - см.
    _REFLECT_PROMPT_MARKER). По умолчанию - валидный PlanOutput с одной search_docs-
    подзадачей и ReflectOutput с "not_in_corpus" (не зацикливаемся на лишний поиск
    в тестах, которые не про reflect)."""
    llm_provider = MagicMock()
    llm_provider.generate = AsyncMock(return_value=llm_answer)

    # generate_node (с 2026-08-05, StreamRunner удалён - см. AGENT_GRAPH_CURRENT.md §1/§2.10)
    # зовёт generate_stream() ВСЕГДА, не только на /llm/answer/stream - generate() остаётся
    # только аварийным fallback'ом на полный сбой стрима (см. test_lean_rag_agent.py::TestRunStream).
    # side_effect - не async-функция сама по себе (не AsyncMock), а обычный callable,
    # возвращающий настоящий async-генератор - так `self.llm_provider.generate_stream(...)`
    # ведёт себя как настоящий provider (вызов синхронный, то, что он вернул - и есть то,
    # что "async for" итерирует), а вызов при этом остаётся инспектируемым через .call_args.
    def _default_generate_stream(*, current_query: str, data_prompt):
        async def _gen():
            yield llm_answer
        return _gen()

    llm_provider.generate_stream = MagicMock(side_effect=_default_generate_stream)

    # plan_node/reflect_node зовут generate_json_raw (JSON-контрактный system-промпт,
    # см. LLM_provider.py/ai_config.toml::json_contract_system_prompt) - generate_general
    # с 2026-08-05 используется только легаси-expand_queries_node (не в живом графе).
    async def _fake_generate_json_raw(*, query: str, temperature: float = 0.2) -> str:
        if _REFLECT_PROMPT_MARKER in query:
            return reflect_response
        return plan_response

    llm_provider.generate_json_raw = AsyncMock(side_effect=_fake_generate_json_raw)
    llm_provider.generate_general = AsyncMock(return_value=plan_response)

    retrieval_service = MagicMock()
    retrieval_service.retrieve = AsyncMock(
        return_value=RetrievalResult(items=retrieval_items or [], total=len(retrieval_items or []))
    )
    # По умолчанию документ без приложений/не найден (None) - тесты, не про A21/appendix,
    # не должны заботиться об этих моках вообще.
    retrieval_service.get_appendix = AsyncMock(return_value=None)
    retrieval_service.find_document_id_by_code = AsyncMock(return_value=None)

    reranker_service = MagicMock()
    if reranker_side_effect is not None:
        reranker_service.rerank = AsyncMock(side_effect=reranker_side_effect)
    else:
        # По умолчанию - identity-порядок с высоким скором (выше rerank_grey_zone_threshold
        # из ai_config.toml), чтобы тесты, не про rerank как таковой, не задевали
        # decide_after_rerank/no_data - см. TestRerankNode для реального поведения.
        async def _default_rerank(*, query, texts):
            return [{"index": i, "score": 0.99} for i in range(len(texts))]

        reranker_service.rerank = AsyncMock(side_effect=_default_rerank)

    return LeanRagAgent(
        llm_provider=llm_provider,
        retrieval_service=retrieval_service,
        reranker_service=reranker_service,
    )


def make_state(**kwargs) -> LeanAgentState:
    defaults = dict(
        query="тестовый запрос",
        messages=[],
        summary="",
        route="domain_rag",
        expanded_queries=["тестовый запрос"],
        retrieval_data=[],
        final_context=None,
        response_model="",
    )
    defaults.update(kwargs)
    return LeanAgentState(**defaults)


def make_retrieve_item(
    parent_chunk: str = "текст родительского чанка",
    child_texts: list[tuple[str, float]] | None = None,
    headers: dict | None = None,
    source: str = "СП 1.13130.pdf",
) -> RetrieveItem:
    chunks = child_texts or [("дочерний чанк 1", 0.92), ("дочерний чанк 2", 0.85)]
    return RetrieveItem(
        parent_chunk=parent_chunk,
        child_chunks=[ChildChunk(text=t, score=s) for t, s in chunks],
        metadata=RetrieveItemMetadata(
            doc_id="doc-1",
            parent_id="parent-1",
            score=0.9,
            headers=headers if headers is not None else {"chapter_number": "1", "title": "1 Общие положения"},
            source=source,
        ),
    )


# ---------------------------------------------------------------------------
# route_node/decide_after_router - удалены 2026-08-06 вместе с query_router
# (см. legacy_disabled_nodes.py), тесты на них удалены тоже.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# expand_queries_node
# ---------------------------------------------------------------------------

class TestExpandQueriesNode:
    @pytest.mark.asyncio
    async def test_original_query_always_in_result(self):
        agent = make_agent(plan_response="вариант1\nвариант2")
        result = await agent.nodes.expand_queries_node(make_state(query="исходный запрос"))
        assert "исходный запрос" in result["expanded_queries"]

    @pytest.mark.asyncio
    async def test_llm_variants_added_to_queries(self):
        agent = make_agent(plan_response="вариант1\nвариант2")
        result = await agent.nodes.expand_queries_node(make_state(query="исходный"))
        assert "вариант1" in result["expanded_queries"]
        assert "вариант2" in result["expanded_queries"]

    @pytest.mark.asyncio
    async def test_calls_llm_generate_general(self):
        agent = make_agent()
        await agent.nodes.expand_queries_node(make_state())
        agent.llm_provider.generate_general.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_duplicates_in_result(self):
        agent = make_agent(plan_response="тестовый запрос\nвариант2")
        result = await agent.nodes.expand_queries_node(make_state(query="тестовый запрос"))
        assert result["expanded_queries"].count("тестовый запрос") == 1

    @pytest.mark.asyncio
    async def test_history_formatted_as_role_content_not_raw_list_repr(self):
        """Регрессия: recent_history раньше подставлялся как сырой list[dict] в .format(),
        что давало "[{'role': 'user', 'content': '...'}]" в промпте на expand LLM-вызов."""
        agent = make_agent()
        state = make_state(messages=[
            {"role": "user", "content": "привет"},
            {"role": "assistant", "content": "здравствуй"},
        ])
        await agent.nodes.expand_queries_node(state)
        prompt_arg = agent.llm_provider.generate_general.call_args.kwargs["query"]
        assert "user: привет" in prompt_arg
        assert "assistant: здравствуй" in prompt_arg
        assert "{'role'" not in prompt_arg


# ---------------------------------------------------------------------------
# retrieve_multi_node
# ---------------------------------------------------------------------------

class TestRetrieveMultiNode:
    @pytest.mark.asyncio
    async def test_returns_items_from_retrieval_result(self):
        item = make_retrieve_item()
        agent = make_agent(retrieval_items=[item])
        result = await agent.nodes.retrieve_multi_node(make_state(expanded_queries=["q"]))
        assert result["retrieval_data"] == [item]

    @pytest.mark.asyncio
    async def test_passes_expanded_queries_to_service(self):
        agent = make_agent()
        queries = ["запрос1", "запрос2", "запрос3"]
        await agent.nodes.retrieve_multi_node(make_state(expanded_queries=queries))
        agent.retrieval_service.retrieve.assert_called_once_with(queries)

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_list(self):
        agent = make_agent(retrieval_items=[])
        result = await agent.nodes.retrieve_multi_node(make_state())
        assert result["retrieval_data"] == []


# ---------------------------------------------------------------------------
# _format_child_chunks_retrive_data
# ---------------------------------------------------------------------------

class TestFormatChildChunks:
    def test_parent_chunk_in_output(self):
        agent = make_agent()
        item = make_retrieve_item(parent_chunk="основной текст раздела")
        assert "основной текст раздела" in formatters.format_retrieval_item_for_prompt(item)

    def test_document_and_title_in_output(self):
        agent = make_agent()
        item = make_retrieve_item(
            source="СП 4.13130.2013 Ограничение распространения пожара.pdf",
            headers={"chapter_number": "5.2", "title": "5.2 Требования к объектам"},
        )
        result = formatters.format_retrieval_item_for_prompt(item)
        assert "СП 4.13130.2013 Ограничение распространения пожара.pdf" in result
        assert "5.2 Требования к объектам" in result

    def test_no_python_dict_repr_in_output(self):
        """Регрессия: раньше в промпт шёл сырой repr headers, напр. "{'chapter_number': '2', ...}"."""
        agent = make_agent()
        item = make_retrieve_item()
        result = formatters.format_retrieval_item_for_prompt(item)
        assert "{'" not in result
        assert "score" not in result.lower()

    def test_missing_title_falls_back_gracefully(self):
        agent = make_agent()
        item = make_retrieve_item(headers={})
        result = formatters.format_retrieval_item_for_prompt(item)
        assert "без названия" in result

    def test_empty_children_no_crash(self):
        agent = make_agent()
        item = RetrieveItem(
            parent_chunk="текст",
            child_chunks=[],
            metadata=RetrieveItemMetadata(doc_id="d", parent_id="p", score=0.9),
        )
        result = formatters.format_retrieval_item_for_prompt(item)
        assert "текст" in result


# ---------------------------------------------------------------------------
# build_prompt_node
# ---------------------------------------------------------------------------

class TestBuildPromptNode:
    @pytest.mark.asyncio
    async def test_returns_final_context(self):
        agent = make_agent()
        result = await agent.nodes.build_prompt_node(make_state())
        assert "final_context" in result
        assert isinstance(result["final_context"], FinalPromptData)

    @pytest.mark.asyncio
    async def test_current_query_mapped(self):
        agent = make_agent()
        result = await agent.nodes.build_prompt_node(make_state(query="мой вопрос"))
        assert result["final_context"].current_query == "мой вопрос"

    @pytest.mark.asyncio
    async def test_summary_mapped(self):
        agent = make_agent()
        result = await agent.nodes.build_prompt_node(make_state(summary="краткое резюме"))
        assert result["final_context"].summary == "краткое резюме"

    @pytest.mark.asyncio
    async def test_retrieval_data_serialized_to_context_str(self):
        agent = make_agent()
        item = make_retrieve_item(parent_chunk="важный раздел документа")
        result = await agent.nodes.build_prompt_node(make_state(retrieval_data=[item]))
        assert "важный раздел документа" in result["final_context"].context

    @pytest.mark.asyncio
    async def test_messages_passed_through_as_list_not_flattened_text(self):
        # Регрессия: chat_history теперь список сырых сообщений (для ролевого
        # массива в LLM_provider.py), не отформатированная строка - LLM_provider
        # сам строит из них отдельные role-сообщения (см. _history_to_messages).
        agent = make_agent()
        messages = [
            {"role": "user", "content": "привет"},
            {"role": "assistant", "content": "здравствуй"},
        ]
        state = make_state(messages=messages)
        result = await agent.nodes.build_prompt_node(state)
        assert result["final_context"].chat_history == messages

    @pytest.mark.asyncio
    async def test_empty_retrieval_gives_empty_context(self):
        agent = make_agent()
        result = await agent.nodes.build_prompt_node(make_state(retrieval_data=[]))
        assert result["final_context"].context == ""

    # A21: reflect_node не вызывается вообще, когда rerank сразу дал "sufficient" - живой
    # прогон подтвердил, что типичный случай (нашли раздел, который ссылается на
    # приложение по имени, с высоким скором) иначе долетал бы до generate() без текста
    # приложения. build_prompt_node - code-gate поверх regex на запрос, подстраховка.
    @pytest.mark.asyncio
    async def test_appendix_mention_in_query_triggers_fallback_fetch(self):
        agent = make_agent()
        agent.retrieval_service.get_appendix = AsyncMock(return_value="текст приложения А")
        item = make_retrieve_item()
        result = await agent.nodes.build_prompt_node(
            make_state(query="что написано в приложении А?", retrieval_data=[item])
        )
        assert "[Приложения документа]" in result["final_context"].context
        assert "текст приложения А" in result["final_context"].context
        agent.retrieval_service.get_appendix.assert_awaited_once_with(item.metadata.doc_id)

    @pytest.mark.asyncio
    async def test_already_set_appendix_context_is_not_refetched(self):
        agent = make_agent()
        agent.retrieval_service.get_appendix = AsyncMock(return_value="СВЕЖИЙ текст")
        item = make_retrieve_item()
        result = await agent.nodes.build_prompt_node(
            make_state(
                query="что в приложении?", retrieval_data=[item], appendix_context="уже подтянуто reflect'ом",
            )
        )
        assert "уже подтянуто reflect'ом" in result["final_context"].context
        agent.retrieval_service.get_appendix.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_appendix_mention_does_not_fetch(self):
        agent = make_agent()
        item = make_retrieve_item()
        result = await agent.nodes.build_prompt_node(
            make_state(query="сроки проведения пусконаладочных работ", retrieval_data=[item])
        )
        assert "[Приложения документа]" not in result["final_context"].context
        agent.retrieval_service.get_appendix.assert_not_called()

    @pytest.mark.asyncio
    async def test_context_mention_resolves_doc_id_from_matching_chunk_not_top_result(self):
        # B6: раньше doc_id брался из топ-1 результата безусловно - в нормативке "см.
        # приложение А" встречается в каждом втором чанке, значит гейт регулярно
        # подтягивал приложение НЕ того документа. Топ-результат (item_top) не
        # упоминает приложение вообще; только второй чанк (item_with_mention) - из
        # ДРУГОГО документа - его ссылается. Должен резолвиться doc-2, не doc-1.
        agent = make_agent()
        agent.retrieval_service.get_appendix = AsyncMock(return_value="текст приложения А")
        item_top = make_retrieve_item(parent_chunk="требования к пусконаладочным работам", source="ГОСТ 1.pdf")
        item_with_mention = make_retrieve_item(
            parent_chunk="подробности см. приложение А", source="СП 1.13130.pdf",
        )
        item_with_mention = item_with_mention.model_copy(
            update={"metadata": item_with_mention.metadata.model_copy(update={"doc_id": "doc-2"})}
        )
        result = await agent.nodes.build_prompt_node(
            make_state(query="какие требования?", retrieval_data=[item_top, item_with_mention])
        )
        assert "[Приложения документа]" in result["final_context"].context
        agent.retrieval_service.get_appendix.assert_awaited_once_with("doc-2")

    @pytest.mark.asyncio
    async def test_query_mention_still_resolves_doc_id_from_top_result(self):
        # Когда упоминание в самом вопросе пользователя (не только в найденном
        # контексте) - top-1 остаётся разумной догадкой, поведение не меняется.
        agent = make_agent()
        agent.retrieval_service.get_appendix = AsyncMock(return_value="текст приложения А")
        item = make_retrieve_item(parent_chunk="без упоминания вообще")
        result = await agent.nodes.build_prompt_node(
            make_state(query="что в приложении А?", retrieval_data=[item])
        )
        agent.retrieval_service.get_appendix.assert_awaited_once_with(item.metadata.doc_id)


# ---------------------------------------------------------------------------
# generate_node
# ---------------------------------------------------------------------------

class TestGenerateNode:
    @pytest.mark.asyncio
    async def test_returns_response_model(self):
        agent = make_agent(llm_answer="готовый ответ")
        final_ctx = FinalPromptData(
            route="domain_rag", context="контекст", chat_history=[],
            summary="резюме", current_query="вопрос",
        )
        result = await agent.nodes.generate_node(make_state(query="вопрос", final_context=final_ctx))
        assert result == {"response_model": "готовый ответ", "response_degraded": False}

    @pytest.mark.asyncio
    async def test_calls_llm_generate_stream_with_correct_args(self):
        # generate_node с 2026-08-05 (StreamRunner удалён) всегда стримит через
        # generate_stream(), не generate() - единый путь для /llm/answer (writer -
        # no-op, дельты просто копятся) и /llm/answer/stream (writer реально доставляет
        # токены наружу), см. AGENT_GRAPH_CURRENT.md §2.10.
        agent = make_agent()
        final_ctx = FinalPromptData(
            route="domain_rag", context="ctx", chat_history=[],
            summary="sum", current_query="q",
        )
        state = make_state(query="q", final_context=final_ctx)
        await agent.nodes.generate_node(state)
        agent.llm_provider.generate_stream.assert_called_once_with(
            current_query="q",
            data_prompt=final_ctx,
        )

    @pytest.mark.asyncio
    async def test_passes_final_context_not_raw_state(self):
        agent = make_agent()
        final_ctx = FinalPromptData(
            route="domain_rag", context="специфический контекст", chat_history=[],
            summary="", current_query="запрос",
        )
        state = make_state(final_context=final_ctx)
        await agent.nodes.generate_node(state)
        call_kwargs = agent.llm_provider.generate_stream.call_args.kwargs
        assert call_kwargs["data_prompt"] is final_ctx


# ---------------------------------------------------------------------------
# run_stream - обрыв соединения с апстрим-LLM не должен терять уже отданные токены
# ---------------------------------------------------------------------------

class TestRunStream:
    @pytest.mark.asyncio
    async def test_yields_tokens_sources_done_on_success(self):
        agent = make_agent(plan_response=_EMPTY_PLAN_RESPONSE)

        async def fake_generate_stream(*, current_query, data_prompt):
            yield "Привет"
            yield ", мир"

        agent.llm_provider.generate_stream = fake_generate_stream

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "status", "token", "token", "sources", "done"]
        assert events[-1]["data"]["answer"] == "Привет, мир"

    @pytest.mark.asyncio
    async def test_marks_partial_answer_interrupted_on_mid_stream_failure(self):
        agent = make_agent(plan_response=_EMPTY_PLAN_RESPONSE)

        async def fake_generate_stream(*, current_query, data_prompt):
            yield "частичный "
            yield "ответ"
            raise ConnectionError("сеть пропала")

        agent.llm_provider.generate_stream = fake_generate_stream

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]

        # Два реальных токена + один токен-пометка об обрыве, дальше как обычно sources/done -
        # исключение НЕ должно всплыть наружу и оборвать SSE-поток без данных для сохранения.
        assert [e["event"] for e in events] == ["status", "status", "token", "token", "token", "sources", "done"]
        final_answer = events[-1]["data"]["answer"]
        assert final_answer.startswith("частичный ответ")
        assert "прерван" in final_answer
        # degraded=True - backend не должен подмешивать это сообщение в историю/саммари
        # следующих ходов (не настоящий полный ответ, а обрыв с пометкой).
        assert events[-1]["data"]["degraded"] is True

    @pytest.mark.asyncio
    async def test_pause_between_deltas_does_not_break_generation(self):
        # Heartbeat теперь целиком на стороне EventSourceResponse (см. agent_routers.py) -
        # run_stream() больше не оборачивает generate_stream() в свою task/wait-машинерию
        # и сам ничего не пингует, так что тут больше нечего проверять про "ping"; осталась
        # только проверка, что пауза между дельтами (напр. сеть подвисла) не ломает сборку
        # ответа при обычном async for.
        agent = make_agent(plan_response=_EMPTY_PLAN_RESPONSE)

        async def fake_generate_stream(*, current_query, data_prompt):
            yield "до паузы"
            await asyncio.sleep(0.02)
            yield "после паузы"

        agent.llm_provider.generate_stream = fake_generate_stream

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]

        assert [e["data"]["text"] for e in events if e["event"] == "token"] == ["до паузы", "после паузы"]
        assert events[-1]["data"]["answer"] == "до паузыпосле паузы"

    @pytest.mark.asyncio
    async def test_falls_back_to_non_streaming_generate_when_zero_tokens_produced(self):
        # Воспроизводит реальный инцидент с gatellm.ru: stream=true падал на 100% запросов
        # (502), а обычный stream=false работал нормально - разовый fallback вместо
        # немедленной сдачи в "ответ прерван".
        agent = make_agent(plan_response=_EMPTY_PLAN_RESPONSE, llm_answer="ответ из фолбэка")

        async def fake_generate_stream(*, current_query, data_prompt):
            if False:
                yield ""
            raise ConnectionError("gateway 502")

        agent.llm_provider.generate_stream = fake_generate_stream

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "status", "token", "sources", "done"]
        assert events[2]["data"]["text"] == "ответ из фолбэка"
        assert events[-1]["data"]["answer"] == "ответ из фолбэка"
        agent.llm_provider.generate.assert_awaited_once()
        # Фолбэк реально сработал - настоящий полный ответ, не деградация.
        assert events[-1]["data"]["degraded"] is False

    @pytest.mark.asyncio
    async def test_slow_fallback_still_returns_answer(self):
        # Heartbeat во время fallback тоже теперь на стороне EventSourceResponse (не
        # unit-тестируется на этом уровне - см. интеграционный live-тест в TODO). Здесь
        # проверяем то, что доступно юнит-тестом: медленный fallback всё равно доходит до
        # конца и отдаёт ответ, а не обрывается из-за отсутствия прежней task-обвязки.
        agent = make_agent(plan_response=_EMPTY_PLAN_RESPONSE)

        async def fake_generate_stream(*, current_query, data_prompt):
            if False:
                yield ""
            raise ConnectionError("gateway 502")

        async def slow_generate(*, current_query, data_prompt):
            await asyncio.sleep(0.02)
            return "медленный ответ из фолбэка"

        agent.llm_provider.generate_stream = fake_generate_stream
        agent.llm_provider.generate = slow_generate

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "status", "token", "sources", "done"]
        assert events[-1]["data"]["answer"] == "медленный ответ из фолбэка"

    @pytest.mark.asyncio
    async def test_fallback_failure_produces_error_note(self):
        agent = make_agent(plan_response=_EMPTY_PLAN_RESPONSE)

        async def fake_generate_stream(*, current_query, data_prompt):
            if False:
                yield ""
            raise ConnectionError("gateway 502")

        agent.llm_provider.generate_stream = fake_generate_stream
        agent.llm_provider.generate = AsyncMock(side_effect=ConnectionError("и обычный вызов тоже упал"))

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "status", "token", "sources", "done"]
        assert "Не удалось получить ответ" in events[-1]["data"]["answer"]
        assert events[-1]["data"]["degraded"] is True

    @pytest.mark.asyncio
    async def test_does_not_fall_back_if_some_tokens_already_shown(self):
        # Отличие от предыдущих двух: тут уже есть частичный ответ - fallback не должен
        # включаться (создал бы вторую, не связанную генерацию поверх показанного текста).
        agent = make_agent(plan_response=_EMPTY_PLAN_RESPONSE)

        async def fake_generate_stream(*, current_query, data_prompt):
            yield "частичный ответ"
            raise ConnectionError("сеть пропала")

        agent.llm_provider.generate_stream = fake_generate_stream

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]

        agent.llm_provider.generate.assert_not_called()
        assert "прерван" in events[-1]["data"]["answer"]


# ---------------------------------------------------------------------------
# rerank/decide_after_rerank - РЕАЛЬНЫЕ с 07.2026 (сознательное исключение из
# eval-ворот, см. ARCHITECTURE.md §1 п.3). no_data теперь тоже достижим.
# ---------------------------------------------------------------------------

class TestRerankNode:
    @pytest.mark.asyncio
    async def test_reorders_by_reranker_score_and_updates_metadata(self):
        item_a = make_retrieve_item(parent_chunk="чанк A")
        item_b = make_retrieve_item(parent_chunk="чанк B")

        async def fake_rerank(*, query, texts):
            # TEI меняет порядок: B релевантнее A
            return [{"index": 1, "score": 0.95}, {"index": 0, "score": 0.1}]

        agent = make_agent(reranker_side_effect=fake_rerank)
        result = await agent.nodes.rerank_node(make_state(retrieval_data=[item_a, item_b]))

        reordered = result["retrieval_data"]
        assert [item.parent_chunk for item in reordered] == ["чанк B", "чанк A"]
        assert reordered[0].metadata.score == 0.95
        assert reordered[1].metadata.score == 0.1

    @pytest.mark.asyncio
    async def test_truncates_to_rerank_final_k(self):
        # 2026-08-06: реранкер до этой правки только пересортировывал, весь пул
        # (включая слабый хвост) доезжал до generate_node - после накопления между
        # кругами reflect пул мог удвоиться. gateway.rerank_final_k = 6 в ai_config.toml.
        items = [make_retrieve_item(parent_chunk=f"чанк {i}") for i in range(8)]

        async def fake_rerank(*, query, texts):
            # Скор убывает с индексом - порядок должен сохраниться после среза.
            return [{"index": i, "score": 1.0 - i * 0.1} for i in range(len(texts))]

        agent = make_agent(reranker_side_effect=fake_rerank)
        result = await agent.nodes.rerank_node(make_state(retrieval_data=items))

        reordered = result["retrieval_data"]
        assert len(reordered) == 6
        assert [item.parent_chunk for item in reordered] == [f"чанк {i}" for i in range(6)]

    @pytest.mark.asyncio
    async def test_empty_retrieval_skips_network_call(self):
        agent = make_agent()
        result = await agent.nodes.rerank_node(make_state(retrieval_data=[]))
        assert result["retrieval_data"] == []
        agent.reranker_service.rerank.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_best_child_chunk_text_not_parent_chunk(self):
        # Регрессия: реранкер должен оценивать короткий child-чанк, который реально
        # совпал при исходном векторном поиске - не parent_chunk целиком (может быть
        # целой главой в тысячи символов, разбавляет сигнал кросс-энкодеру и рискует
        # не влезть в его контекст/раздуть латентность).
        item = make_retrieve_item(
            parent_chunk="родительский текст на тысячи символов" * 100,
            child_texts=[("слабый чанк", 0.3), ("лучший чанк", 0.9)],
        )
        agent = make_agent()
        await agent.nodes.rerank_node(make_state(retrieval_data=[item]))
        call_kwargs = agent.reranker_service.rerank.call_args.kwargs
        assert call_kwargs["texts"] == ["лучший чанк"]

    @pytest.mark.asyncio
    async def test_falls_back_to_parent_chunk_when_no_child_chunks(self):
        item = RetrieveItem(
            parent_chunk="только родительский текст",
            child_chunks=[],
            metadata=RetrieveItemMetadata(doc_id="d", parent_id="p", score=0.9),
        )
        agent = make_agent()
        await agent.nodes.rerank_node(make_state(retrieval_data=[item]))
        call_kwargs = agent.reranker_service.rerank.call_args.kwargs
        assert call_kwargs["texts"] == ["только родительский текст"]

    @pytest.mark.asyncio
    async def test_reranks_against_plan_query_not_raw_state_query(self):
        # Живой баг: один и тот же кусок получал 0.004 против сырого state.query
        # ("какие меры применимы при нарушении" - нарушении чего, неясно вне контекста)
        # и 0.85 против запроса, который plan_node уже расшифровал для retrieval
        # ("меры при нарушении генподрядчиком пусконаладочных работ"). Реранк должен
        # сравнивать с тем же текстом, каким реально искали, а не с сырым вопросом.
        item = make_retrieve_item()
        plan = PlanOutput(subtasks=[
            PlanSubtask(tool="search_docs", args={"queries": ["расшифрованный запрос"]}),
        ])
        agent = make_agent()
        await agent.nodes.rerank_node(
            make_state(query="сырой вопрос", retrieval_data=[item], plan=plan)
        )
        call_kwargs = agent.reranker_service.rerank.call_args.kwargs
        assert call_kwargs["query"] == "расшифрованный запрос"

    @pytest.mark.asyncio
    async def test_reranks_against_raw_query_when_no_plan(self):
        item = make_retrieve_item()
        agent = make_agent()
        await agent.nodes.rerank_node(make_state(query="сырой вопрос", retrieval_data=[item], plan=None))
        call_kwargs = agent.reranker_service.rerank.call_args.kwargs
        assert call_kwargs["query"] == "сырой вопрос"

    @pytest.mark.asyncio
    async def test_reranks_against_search_docs_query_when_get_appendix_is_first_subtask(self):
        # B5: subtasks[0].args.get("query", ...) слепо брало первую подзадачу - если это
        # get_appendix (args: {"document_code"}, без "queries"), rerank_query тихо
        # откатывался на сырой state.query, воспроизводя баг из
        # test_reranks_against_plan_query_not_raw_state_query заново для планов вида
        # [get_appendix, search_docs].
        item = make_retrieve_item()
        plan = PlanOutput(subtasks=[
            PlanSubtask(tool="get_appendix", args={"document_code": "СП 1.13130"}),
            PlanSubtask(tool="search_docs", args={"queries": ["расшифрованный запрос"]}),
        ])
        agent = make_agent()
        await agent.nodes.rerank_node(
            make_state(query="сырой вопрос", retrieval_data=[item], plan=plan)
        )
        call_kwargs = agent.reranker_service.rerank.call_args.kwargs
        assert call_kwargs["query"] == "расшифрованный запрос"

    @pytest.mark.asyncio
    async def test_reranks_against_latest_query_not_concatenated(self):
        # 2026-08-06: bge-reranker-v2-m3 обучен на парах "один запрос - один пассаж" -
        # склейка нескольких формулировок в одну строку - данные вне распределения
        # обучения. Реранк должен сравнивать с АКТУАЛЬНОЙ (последней) формулировкой,
        # не со смесью всех.
        item = make_retrieve_item()
        plan = PlanOutput(subtasks=[
            PlanSubtask(tool="search_docs", args={"queries": ["запрос один", "запрос два"]}),
        ])
        agent = make_agent()
        await agent.nodes.rerank_node(
            make_state(query="сырой вопрос", retrieval_data=[item], plan=plan)
        )
        call_kwargs = agent.reranker_service.rerank.call_args.kwargs
        assert call_kwargs["query"] == "запрос два"

    @pytest.mark.asyncio
    async def test_reranks_against_latest_query_across_multiple_subtasks(self):
        # Защитный случай: даже если формулировки почему-то оказались в РАЗНЫХ
        # search_docs-подзадачах (не одна подзадача со списком), rerank_query всё
        # равно должен взять последнюю по порядку, а не первую.
        item = make_retrieve_item()
        plan = PlanOutput(subtasks=[
            PlanSubtask(tool="search_docs", args={"queries": ["запрос один"]}),
            PlanSubtask(tool="search_docs", args={"queries": ["запрос два"]}),
        ])
        agent = make_agent()
        await agent.nodes.rerank_node(
            make_state(query="сырой вопрос", retrieval_data=[item], plan=plan)
        )
        call_kwargs = agent.reranker_service.rerank.call_args.kwargs
        assert call_kwargs["query"] == "запрос два"


class TestDecideAfterRerank:
    @pytest.mark.asyncio
    async def test_empty_retrieval_returns_empty(self):
        agent = make_agent()
        assert await decisions.decide_after_rerank(make_state(retrieval_data=[])) == "empty"

    @pytest.mark.asyncio
    async def test_score_below_no_data_threshold_returns_empty(self):
        # Порог из ai_config.toml: rerank_no_data_threshold = 0.35
        agent = make_agent()
        item = make_retrieve_item()
        item.metadata.score = 0.2
        assert await decisions.decide_after_rerank(make_state(retrieval_data=[item])) == "empty"

    @pytest.mark.asyncio
    async def test_score_in_grey_zone_returns_grey_zone(self):
        # Между rerank_no_data_threshold (0.35) и rerank_grey_zone_threshold (0.60)
        agent = make_agent()
        item = make_retrieve_item()
        item.metadata.score = 0.5
        assert await decisions.decide_after_rerank(make_state(retrieval_data=[item])) == "grey_zone"

    @pytest.mark.asyncio
    async def test_score_above_grey_zone_returns_sufficient(self):
        agent = make_agent()
        item = make_retrieve_item()
        item.metadata.score = 0.9
        assert await decisions.decide_after_rerank(make_state(retrieval_data=[item])) == "sufficient"


class TestNoDataNode:
    @pytest.mark.asyncio
    async def test_returns_honest_refusal_without_calling_llm(self):
        agent = make_agent()
        result = await agent.nodes.no_data_node(make_state())
        assert result["retrieval_empty"] is True
        assert result["response_model"]
        agent.llm_provider.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_clears_retrieval_data(self):
        # A7: reflect_node может выставить not_in_corpus при непустом (просто слабом)
        # retrieval_data - без очистки здесь extract_sources_node строил бы источники
        # рядом с "в базе знаний нет информации", что читается как противоречие.
        agent = make_agent()
        item = make_retrieve_item()
        result = await agent.nodes.no_data_node(make_state(retrieval_data=[item]))
        assert result["retrieval_data"] == []


# ---------------------------------------------------------------------------
# Остальные новые ноды-заглушки (ARCHITECTURE.md) - детерминированный no-op
# контракт, reflect/personal/plan/... по-прежнему не реализованы.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# plan_node - РЕАЛЬНЫЙ с отключением ML-роутера (см. _build_graph/ISSUES.md),
# точка входа графа вместо router.
# ---------------------------------------------------------------------------

class TestPlanNode:
    @pytest.mark.asyncio
    async def test_default_response_produces_search_docs_subtask(self):
        agent = make_agent()
        result = await agent.nodes.plan_node(make_state(query="что такое редуктор?"))
        plan = result["plan"]
        assert len(plan.subtasks) == 1
        assert plan.subtasks[0].tool == "search_docs"

    @pytest.mark.asyncio
    async def test_empty_plan_response_produces_no_subtasks(self):
        agent = make_agent(plan_response=_EMPTY_PLAN_RESPONSE)
        result = await agent.nodes.plan_node(make_state(query="привет"))
        assert result["plan"].subtasks == []

    @pytest.mark.asyncio
    async def test_truncates_to_max_subtasks(self):
        # gateway.max_subtasks = 4 в ai_config.toml - если LLM предложит больше,
        # обрезаем, а не исполняем всё подряд (execute_subtasks последовательный,
        # не asyncio.gather - см. AGENT_GRAPH_CURRENT.md §6.5).
        many_subtasks = ", ".join(
            '{"tool": "search_docs", "args": {"queries": ["q%d"], "doc_filter": null}}' % i
            for i in range(15)
        )
        agent = make_agent(plan_response='{"subtasks": [%s], "synthesis": ""}' % many_subtasks)
        result = await agent.nodes.plan_node(make_state())
        assert len(result["plan"].subtasks) == 4

    @pytest.mark.asyncio
    async def test_history_formatted_as_role_content_not_raw_list_repr(self):
        agent = make_agent()
        state = make_state(messages=[
            {"role": "user", "content": "привет"},
            {"role": "assistant", "content": "здравствуй"},
        ])
        await agent.nodes.plan_node(state)
        prompt_arg = agent.llm_provider.generate_json_raw.call_args.kwargs["query"]
        assert "Пользователь: привет" in prompt_arg
        assert "Ассистент: здравствуй" in prompt_arg
        assert "{'role'" not in prompt_arg

    @pytest.mark.asyncio
    async def test_falls_back_to_default_search_plan_on_llm_failure(self):
        # plan_node - точка входа 100% живого трафика (включая "привет"/"спасибо",
        # которые вообще не требовали бы LLM). Раньше невалидный JSON/таймаут/5xx
        # апстрима здесь означал голый 500 даже на светскую беседу - деградируем до
        # обычного search_docs по сырому вопросу вместо того, чтобы ронять весь ответ.
        agent = make_agent()
        agent.llm_provider.generate_json_raw = AsyncMock(side_effect=RuntimeError("upstream 500"))
        before = planning_nodes.PLAN_FALLBACK_COUNT._value.get()

        result = await agent.nodes.plan_node(make_state(query="сырой вопрос пользователя"))

        plan = result["plan"]
        assert len(plan.subtasks) == 1
        assert plan.subtasks[0].tool == "search_docs"
        assert plan.subtasks[0].args["queries"] == ["сырой вопрос пользователя"]
        assert result["route"] == "domain_rag"
        assert planning_nodes.PLAN_FALLBACK_COUNT._value.get() == before + 1

    @pytest.mark.asyncio
    async def test_query_included_in_prompt(self):
        agent = make_agent()
        await agent.nodes.plan_node(make_state(query="уникальный вопрос про редуктор"))
        prompt_arg = agent.llm_provider.generate_json_raw.call_args.kwargs["query"]
        assert "уникальный вопрос про редуктор" in prompt_arg

    # route теперь производная от решения plan (нужен ли поиск), а не захардкоженное
    # значение - см. planning_nodes.py::plan_node. Без этого generate_node никогда не
    # выбирал бы system_prompt_chat (route всегда был "domain_rag").
    @pytest.mark.asyncio
    async def test_non_empty_plan_sets_domain_rag_route(self):
        agent = make_agent()
        result = await agent.nodes.plan_node(make_state(query="что такое редуктор?"))
        assert result["route"] == "domain_rag"

    @pytest.mark.asyncio
    async def test_empty_plan_sets_smalltalk_route(self):
        agent = make_agent(plan_response=_EMPTY_PLAN_RESPONSE)
        result = await agent.nodes.plan_node(make_state(query="привет"))
        assert result["route"] == "smalltalk"


class TestDecideAfterReflect:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("verdict", ["sufficient", "need_more", "not_in_corpus"])
    async def test_returns_state_verdict(self, verdict):
        assert await decisions.decide_after_reflect(make_state(reflect_verdict=verdict)) == verdict

    @pytest.mark.asyncio
    async def test_defaults_to_sufficient_when_no_verdict_set(self):
        assert await decisions.decide_after_reflect(make_state(reflect_verdict=None)) == "sufficient"


class TestReflectNode:
    @pytest.mark.asyncio
    async def test_sufficient_verdict(self):
        agent = make_agent(reflect_response='{"verdict": "sufficient", "new_queries": []}')
        item = make_retrieve_item()
        result = await agent.nodes.reflect_node(make_state(retrieval_data=[item], reflect_rounds=0))
        assert result["reflect_verdict"] == "sufficient"
        assert result["reflect_rounds"] == 1
        assert "plan" not in result

    @pytest.mark.asyncio
    async def test_not_in_corpus_verdict(self):
        agent = make_agent(reflect_response='{"verdict": "not_in_corpus", "new_queries": []}')
        result = await agent.nodes.reflect_node(make_state(retrieval_data=[], reflect_rounds=0))
        assert result["reflect_verdict"] == "not_in_corpus"

    @pytest.mark.asyncio
    async def test_need_more_builds_new_plan_from_queries(self):
        # Живой сценарий, который и просил пользователь: reflect смотрит на найденное
        # и генерирует уточняющие запросы - они должны стать новым state.plan, который
        # execute_subtasks_node подхватит на повторном заходе без спец-обработки.
        agent = make_agent(
            reflect_response='{"verdict": "need_more", "new_queries": ["запрос1", "запрос2"]}'
        )
        result = await agent.nodes.reflect_node(make_state(retrieval_data=[], reflect_rounds=0))
        assert result["reflect_verdict"] == "need_more"
        new_plan = result["plan"]
        # Одна подзадача со списком формулировок (не подзадача на каждую) - rag_service
        # батчит их одним вызовом, см. tool_registry.py::SearchDocsArgs.
        assert [st.tool for st in new_plan.subtasks] == ["search_docs"]
        assert new_plan.subtasks[0].args["queries"] == ["запрос1", "запрос2"]

    @pytest.mark.asyncio
    async def test_need_more_without_new_queries_falls_back_to_sufficient_if_something_found(self):
        agent = make_agent(reflect_response='{"verdict": "need_more", "new_queries": []}')
        item = make_retrieve_item()
        result = await agent.nodes.reflect_node(make_state(retrieval_data=[item], reflect_rounds=0))
        assert result["reflect_verdict"] == "sufficient"

    @pytest.mark.asyncio
    async def test_need_more_without_new_queries_falls_back_to_not_in_corpus_if_empty(self):
        agent = make_agent(reflect_response='{"verdict": "need_more", "new_queries": []}')
        result = await agent.nodes.reflect_node(make_state(retrieval_data=[], reflect_rounds=0))
        assert result["reflect_verdict"] == "not_in_corpus"

    @pytest.mark.asyncio
    async def test_second_round_caps_without_calling_llm(self):
        # Уже был один круг уточнения (reflect_rounds=1) - не зовём LLM снова, не
        # зацикливаемся дальше.
        agent = make_agent()
        item = make_retrieve_item()
        result = await agent.nodes.reflect_node(make_state(retrieval_data=[item], reflect_rounds=1))
        assert result["reflect_verdict"] == "sufficient"
        assert result["reflect_rounds"] == 2
        agent.llm_provider.generate_json_raw.assert_not_called()

    @pytest.mark.asyncio
    async def test_second_round_cap_with_empty_retrieval_is_not_in_corpus(self):
        agent = make_agent()
        result = await agent.nodes.reflect_node(make_state(retrieval_data=[], reflect_rounds=1))
        assert result["reflect_verdict"] == "not_in_corpus"
        agent.llm_provider.generate_json_raw.assert_not_called()

    @pytest.mark.asyncio
    async def test_prompt_includes_query_and_found_content(self):
        agent = make_agent(reflect_response='{"verdict": "sufficient", "new_queries": []}')
        item = make_retrieve_item(parent_chunk="уникальный текст найденного фрагмента")
        await agent.nodes.reflect_node(make_state(query="уникальный вопрос", retrieval_data=[item]))
        prompt_arg = agent.llm_provider.generate_json_raw.call_args.kwargs["query"]
        assert "уникальный вопрос" in prompt_arg
        assert "уникальный текст найденного фрагмента" in prompt_arg

    @pytest.mark.asyncio
    async def test_prompt_marks_empty_retrieval(self):
        agent = make_agent(reflect_response='{"verdict": "not_in_corpus", "new_queries": []}')
        await agent.nodes.reflect_node(make_state(retrieval_data=[]))
        prompt_arg = agent.llm_provider.generate_json_raw.call_args.kwargs["query"]
        assert "ничего не найдено" in prompt_arg

    @pytest.mark.asyncio
    async def test_prompt_includes_tried_queries_and_their_score(self):
        # RL-фрейминг: reflect должен видеть не только НАЙДЕННОЕ, но и КАКИМИ
        # ЗАПРОСАМИ уже искали - иначе не отличит "первая формулировка была почти
        # правильной" от "нужен принципиально другой заход" и предложит new_queries,
        # близкие по смыслу к уже провалившимся.
        agent = make_agent(reflect_response='{"verdict": "need_more", "new_queries": ["другой заход"]}')
        item = make_retrieve_item()
        item.metadata.score = 0.42
        plan = PlanOutput(subtasks=[
            PlanSubtask(tool="search_docs", args={"queries": ["первая формулировка", "вторая формулировка"]}),
        ])
        await agent.nodes.reflect_node(make_state(retrieval_data=[item], plan=plan))
        prompt_arg = agent.llm_provider.generate_json_raw.call_args.kwargs["query"]
        assert "первая формулировка" in prompt_arg
        assert "вторая формулировка" in prompt_arg
        assert "0.42" in prompt_arg

    @pytest.mark.asyncio
    async def test_prompt_marks_no_queries_tried_when_no_plan(self):
        agent = make_agent(reflect_response='{"verdict": "not_in_corpus", "new_queries": []}')
        await agent.nodes.reflect_node(make_state(retrieval_data=[], plan=None))
        prompt_arg = agent.llm_provider.generate_json_raw.call_args.kwargs["query"]
        assert "поиск ещё не выполнялся" in prompt_arg

    # A21 (rag_service/ISSUES.md): приложения не проиндексированы, reflect подтягивает
    # их текст напрямую через RetrievalService.get_appendix, когда LLM выставляет
    # needs_appendix - независимо от verdict.
    @pytest.mark.asyncio
    async def test_needs_appendix_fetches_and_sets_appendix_context(self):
        agent = make_agent(
            reflect_response='{"verdict": "sufficient", "new_queries": [], "needs_appendix": true}'
        )
        agent.retrieval_service.get_appendix = AsyncMock(return_value="текст приложения А")
        item = make_retrieve_item()
        result = await agent.nodes.reflect_node(make_state(retrieval_data=[item], reflect_rounds=0))
        assert result["appendix_context"] == "текст приложения А"
        agent.retrieval_service.get_appendix.assert_awaited_once_with(item.metadata.doc_id)

    @pytest.mark.asyncio
    async def test_needs_appendix_false_does_not_fetch(self):
        agent = make_agent(reflect_response='{"verdict": "sufficient", "new_queries": []}')
        item = make_retrieve_item()
        result = await agent.nodes.reflect_node(make_state(retrieval_data=[item], reflect_rounds=0))
        assert "appendix_context" not in result
        agent.retrieval_service.get_appendix.assert_not_called()

    @pytest.mark.asyncio
    async def test_needs_appendix_true_but_no_retrieval_data_does_not_fetch(self):
        # Нечего резолвить doc_id из - retrieval_data пуст.
        agent = make_agent(
            reflect_response='{"verdict": "not_in_corpus", "new_queries": [], "needs_appendix": true}'
        )
        result = await agent.nodes.reflect_node(make_state(retrieval_data=[], reflect_rounds=0))
        assert "appendix_context" not in result
        agent.retrieval_service.get_appendix.assert_not_called()


class TestNewStubNodesAreInert:
    @pytest.mark.asyncio
    async def test_resolve_docs_node_returns_empty(self):
        agent = make_agent()
        assert await agent.nodes.resolve_docs_node(make_state()) == {"resolved_docs": []}

    @pytest.mark.asyncio
    async def test_personal_search_node_returns_empty_retrieval(self):
        agent = make_agent()
        assert await agent.nodes.personal_search_node(make_state()) == {"retrieval_data": []}

    @pytest.mark.asyncio
    async def test_gather_passports_node_returns_empty(self):
        agent = make_agent()
        assert await agent.nodes.gather_passports_node(make_state()) == {"document_passports": []}

    @pytest.mark.asyncio
    async def test_post_actions_node_never_produces_action(self):
        agent = make_agent()
        assert await agent.nodes.post_actions_node(make_state()) == {"proposed_action": None}


class TestDecideAfterResolveDocs:
    @pytest.mark.asyncio
    async def test_zero_docs_goes_to_clarify(self):
        agent = make_agent()
        assert await agent.nodes.decide_after_resolve_docs(make_state(resolved_docs=[])) == "clarify"

    @pytest.mark.asyncio
    async def test_over_threshold_goes_to_background(self):
        agent = make_agent()
        many_docs = [f"doc-{i}" for i in range(10)]
        assert await agent.nodes.decide_after_resolve_docs(make_state(resolved_docs=many_docs)) == "background"

    @pytest.mark.asyncio
    async def test_within_threshold_goes_to_gather_passports(self):
        agent = make_agent()
        docs = ["doc-1", "doc-2"]
        assert await agent.nodes.decide_after_resolve_docs(make_state(resolved_docs=docs)) == "gather_passports"


class TestExecuteSubtasksNode:
    @pytest.mark.asyncio
    async def test_dispatches_read_tool_and_collects_result(self):
        item = make_retrieve_item()
        agent = make_agent(retrieval_items=[item])
        plan = PlanOutput(subtasks=[PlanSubtask(tool="search_docs", args={"queries": ["test"]})])
        result = await agent.nodes.execute_subtasks_node(make_state(plan=plan))
        assert len(result["subtask_results"]) == 1
        assert result["subtask_results"][0]["tool"] == "search_docs"

    @pytest.mark.asyncio
    async def test_refuses_write_tool(self):
        # Регрессия ARCHITECTURE.md §8 Excessive Agency: даже если plan когда-нибудь
        # ошибочно предложит write-инструмент, диспетчер не должен его исполнять.
        agent = make_agent()
        plan = PlanOutput(subtasks=[PlanSubtask(tool="create_note", args={"title": "t", "content": "c"})])
        result = await agent.nodes.execute_subtasks_node(make_state(plan=plan))
        assert result["subtask_results"] == []

    @pytest.mark.asyncio
    async def test_unknown_tool_skipped_not_raised(self):
        agent = make_agent()
        plan = PlanOutput(subtasks=[PlanSubtask(tool="not_a_real_tool", args={})])
        result = await agent.nodes.execute_subtasks_node(make_state(plan=plan))
        assert result["subtask_results"] == []

    @pytest.mark.asyncio
    async def test_no_plan_returns_empty_results(self):
        agent = make_agent()
        result = await agent.nodes.execute_subtasks_node(make_state(plan=None))
        assert result["subtask_results"] == []

    @pytest.mark.asyncio
    async def test_search_docs_results_merged_into_retrieval_data(self):
        # Регрессия: раньше execute_subtasks_node возвращал только subtask_results,
        # а rerank_node/build_prompt_node читают retrieval_data - без слияния
        # найденные документы молча терялись бы (никогда не был живым трафиком до
        # отключения ML-роутера, поэтому не был пойман раньше).
        item = make_retrieve_item()
        agent = make_agent(retrieval_items=[item])
        plan = PlanOutput(subtasks=[PlanSubtask(tool="search_docs", args={"queries": ["test"]})])
        result = await agent.nodes.execute_subtasks_node(make_state(plan=plan))
        assert result["retrieval_data"] == [item]

    @pytest.mark.asyncio
    async def test_multiple_queries_in_one_search_docs_subtask_go_in_a_single_retrieve_call(self):
        # 2026-08-06: search_docs.queries - список, rag_service уже умеет батчить
        # несколько формулировок одним вызовом эмбеддера + одним batch-запросом в
        # Qdrant (RetrieveService.batch_search) - та же труба, что раньше использовал
        # legacy retrieve_multi_node. До этой правки каждая формулировка была отдельной
        # search_docs-подзадачей, execute_subtasks_node звал tool.fn N раз
        # последовательно (N HTTP round-trip'ов) вместо одного батч-вызова.
        item = make_retrieve_item()
        agent = make_agent(retrieval_items=[item])
        plan = PlanOutput(subtasks=[
            PlanSubtask(tool="search_docs", args={"queries": ["формулировка 1", "формулировка 2"]}),
        ])

        await agent.nodes.execute_subtasks_node(make_state(plan=plan))

        agent.retrieval_service.retrieve.assert_awaited_once_with(
            ["формулировка 1", "формулировка 2"], top_k_per_query=3, max_parents=6,
        )

    @pytest.mark.asyncio
    async def test_multiple_search_docs_subtasks_deduplicated_by_parent_id(self):
        # Две search_docs-подзадачи (разные формулировки одного плана) находят один
        # и тот же parent_id с разным score - должен остаться только более высокий.
        low = make_retrieve_item(parent_chunk="низкий скор")
        low.metadata.score = 0.3
        high = make_retrieve_item(parent_chunk="высокий скор")
        high.metadata.score = 0.9  # тот же parent_id ("parent-1" по умолчанию)

        call_results = [
            RetrievalResult(items=[low], total=1),
            RetrievalResult(items=[high], total=1),
        ]
        agent = make_agent()
        agent.retrieval_service.retrieve = AsyncMock(side_effect=call_results)

        plan = PlanOutput(subtasks=[
            PlanSubtask(tool="search_docs", args={"queries": ["q1"]}),
            PlanSubtask(tool="search_docs", args={"queries": ["q2"]}),
        ])
        result = await agent.nodes.execute_subtasks_node(make_state(plan=plan))

        assert len(result["retrieval_data"]) == 1
        assert result["retrieval_data"][0].metadata.score == 0.9

    @pytest.mark.asyncio
    async def test_accumulates_with_previous_round_retrieval_data(self):
        # RL-фрейминг: агент не должен терять то, что нашёл на предыдущем круге
        # (reflect need_more -> execute_subtasks_node вызывается снова) - копим и
        # выбираем лучшее из всего, а не подменяем целиком последним кругом.
        prior_item = make_retrieve_item(parent_chunk="из первого круга")
        prior_item = prior_item.model_copy(
            update={"metadata": prior_item.metadata.model_copy(update={"parent_id": "parent-old"})}
        )
        new_item = make_retrieve_item(parent_chunk="из второго круга")  # parent_id="parent-1" по умолчанию
        agent = make_agent(retrieval_items=[new_item])
        plan = PlanOutput(subtasks=[PlanSubtask(tool="search_docs", args={"queries": ["уточнённый запрос"]})])

        result = await agent.nodes.execute_subtasks_node(make_state(plan=plan, retrieval_data=[prior_item]))

        parent_ids = {item.metadata.parent_id for item in result["retrieval_data"]}
        assert parent_ids == {"parent-old", "parent-1"}

    @pytest.mark.asyncio
    async def test_accumulation_deduplicates_by_parent_id_keeping_fresh_version(self):
        # 2026-08-06: тот же parent_id найден и в первом, и во втором круге - свежая
        # версия побеждает безусловно, без сравнения score. У прежнего элемента score
        # уже калиброванный (0..1 кросс-энкодера из rerank_node прошлого круга), у
        # свежего - сырой fusion-скор из rag_service (другая шкала) - сравнивать их
        # напрямую бессмысленно, а объединённый пул всё равно уйдёт на пересчёт в
        # rerank_node сразу после этой ноды.
        prior_item = make_retrieve_item(parent_chunk="старая версия")
        prior_item.metadata.score = 0.9  # выше, чем у свежей - и всё равно не побеждает
        new_item = make_retrieve_item(parent_chunk="новая версия")  # тот же parent_id
        new_item.metadata.score = 0.2
        agent = make_agent(retrieval_items=[new_item])
        plan = PlanOutput(subtasks=[PlanSubtask(tool="search_docs", args={"queries": ["q"]})])

        result = await agent.nodes.execute_subtasks_node(make_state(plan=plan, retrieval_data=[prior_item]))

        assert len(result["retrieval_data"]) == 1
        assert result["retrieval_data"][0].parent_chunk == "новая версия"

    # get_appendix - реальный тул с 2026-08-05 (см. tool_registry.py), но его результат
    # не "search-результат" (нет score, не чанк) - идёт в отдельное поле appendix_context,
    # не в retrieval_data (merge_search_docs_results его игнорирует).
    @pytest.mark.asyncio
    async def test_get_appendix_result_goes_to_appendix_context_not_retrieval_data(self):
        agent = make_agent()
        agent.retrieval_service.find_document_id_by_code = AsyncMock(return_value="doc-1")
        agent.retrieval_service.get_appendix = AsyncMock(return_value="текст приложения А")
        plan = PlanOutput(subtasks=[PlanSubtask(tool="get_appendix", args={"document_code": "СП 1.13130"})])

        result = await agent.nodes.execute_subtasks_node(make_state(plan=plan))

        assert result["appendix_context"] == "текст приложения А"
        assert result["retrieval_data"] == []

    @pytest.mark.asyncio
    async def test_get_appendix_no_result_does_not_set_appendix_context_key(self):
        # Не найдено (document_code не резолвился) - appendix_context не должен попасть
        # в update вообще, иначе затёр бы значение, выставленное на предыдущем круге.
        agent = make_agent()
        agent.retrieval_service.find_document_id_by_code = AsyncMock(return_value=None)
        plan = PlanOutput(subtasks=[PlanSubtask(tool="get_appendix", args={"document_code": "неизвестно"})])

        result = await agent.nodes.execute_subtasks_node(make_state(plan=plan))

        assert "appendix_context" not in result


class TestDecideAfterExecuteSubtasks:
    @pytest.mark.asyncio
    async def test_search_docs_result_routes_to_rerank(self):
        agent = make_agent()
        state = make_state(subtask_results=[{"tool": "search_docs", "result": {}}])
        assert await decisions.decide_after_execute_subtasks(state) == "rerank"

    @pytest.mark.asyncio
    async def test_no_search_docs_routes_to_build_prompt(self):
        agent = make_agent()
        assert await decisions.decide_after_execute_subtasks(make_state(subtask_results=[])) == "build_prompt"


class TestExtractSourcesNode:
    @pytest.mark.asyncio
    async def test_matches_build_sources_output(self):
        agent = make_agent()
        item = make_retrieve_item()
        result = await agent.nodes.extract_sources_node(make_state(retrieval_data=[item]))
        assert result["sources"] == LeanRagAgent.build_sources([item])


class TestDecideAfterGenerate:
    @pytest.mark.asyncio
    async def test_smalltalk_without_marker_ends(self):
        agent = make_agent()
        state = make_state(route="smalltalk", query="привет, как дела?")
        assert await decisions.decide_after_generate(state) == "end"

    @pytest.mark.asyncio
    async def test_smalltalk_with_marker_goes_to_post_actions(self):
        # route="smalltalk" теперь означает "plan решил не искать по базе" (см.
        # planning_nodes.py::plan_node), не "точно не про действие" - запрос-действие
        # без похода в базу ("сохрани это в заметку" без доп. контекста) тоже мог бы
        # получить route="smalltalk". Маркер действия должен сработать независимо от route.
        agent = make_agent()
        state = make_state(route="smalltalk", query="сохрани это в заметку")
        assert await decisions.decide_after_generate(state) == "post_actions"

    @pytest.mark.asyncio
    async def test_domain_rag_without_marker_ends(self):
        agent = make_agent()
        state = make_state(route="domain_rag", query="что такое редуктор?")
        assert await decisions.decide_after_generate(state) == "end"

    @pytest.mark.asyncio
    async def test_domain_rag_with_marker_goes_to_post_actions(self):
        agent = make_agent()
        state = make_state(route="domain_rag", query="сохрани это в заметку")
        assert await decisions.decide_after_generate(state) == "post_actions"


# ---------------------------------------------------------------------------
# Полный граф для domain_rag/smalltalk/out_of_domain: с 07.2026 rerank реален
# (сознательное исключение из eval-ворот), поэтому "байт-в-байт" по score больше
# не гарантируется - но состав/порядок контента и то, что новые LLM-зависимые
# заглушки (reflect/post_actions/resolve_docs/plan) не трогаются на happy-path,
# по-прежнему должно выполняться.
# ---------------------------------------------------------------------------

class TestFullGraphByteForByteRegression:
    @pytest.mark.asyncio
    async def test_domain_rag_full_graph_matches_expected_answer_and_sources(self):
        item = make_retrieve_item(parent_chunk="важный раздел документа")
        agent = make_agent(llm_answer="итоговый ответ", retrieval_items=[item])

        inputs = LeanAgentState(
            query="вопрос", messages=[], summary="", route="domain_rag", expanded_queries=["вопрос"],
        )
        final_state = await agent.app.ainvoke(inputs)

        assert final_state["response_model"] == "итоговый ответ"
        # Содержимое совпадает, но score теперь честно переписан реальным rerank_node
        # (make_agent по умолчанию мокает reranker на identity-порядок со скором 0.99).
        assert len(final_state["retrieval_data"]) == 1
        assert final_state["retrieval_data"][0].parent_chunk == item.parent_chunk
        assert final_state["retrieval_data"][0].metadata.score == 0.99
        assert final_state["sources"] == LeanRagAgent.build_sources(final_state["retrieval_data"])

    @pytest.mark.asyncio
    async def test_empty_retrieval_routes_through_reflect_to_no_data_on_compiled_graph(self):
        # Регрессия на graph_builder.py: decide_after_rerank теперь мапит "empty" на
        # "reflect", не на "no_data" напрямую - без этого граф расходился бы с
        # run_stream(), где та же логика была бы явно.
        agent = make_agent()  # retrieval_items=None -> пустой поиск -> "empty"
        inputs = LeanAgentState(
            query="вопрос", messages=[], summary="", route="domain_rag", expanded_queries=["вопрос"],
        )
        final_state = await agent.app.ainvoke(inputs)

        assert final_state["retrieval_empty"] is True
        assert final_state["reflect_rounds"] == 1
        agent.llm_provider.generate.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("plan_response", [_DEFAULT_PLAN_RESPONSE, _EMPTY_PLAN_RESPONSE])
    async def test_full_graph_never_touches_disabled_router_nodes(self, plan_response):
        """С отключением ML-роутера (см. _build_graph) plan_node/execute_subtasks_node
        теперь ВСЕГДА на живом пути - это больше не "мёртвый код". route_node/
        decide_after_router удалены совсем (2026-08-06, не просто отключены).
        Остальное - expand_queries/retrieve_multi/personal_search/resolve_docs/
        gather_passports - всё ещё методы класса (см. docstring _build_graph),
        просто не в графе. no_data/reflect/post_actions остаются недостижимыми на
        happy-path независимо от плана (высокий score от дефолтного реранкера, нет
        action-маркера в запросе)."""
        item = make_retrieve_item()
        agent = make_agent(plan_response=plan_response, retrieval_items=[item])
        inputs = LeanAgentState(
            query="вопрос", messages=[], summary="", route="domain_rag", expanded_queries=["вопрос"],
        )

        # ВАЖНО: plan_node/execute_subtasks_node НЕ спаим здесь - LangGraph захватывает
        # оригинальный bound-метод в момент self._build_graph() (в __init__, до этого
        # patch.object), так что подмена self.plan_node постфактум не перехватывает
        # вызовы внутри agent.app.ainvoke(). Для нод, реально входящих в граф, это
        # нужно проверять по наблюдаемым эффектам (ниже), не спаем на них - для нод,
        # которых в графе НЕТ вообще (expand_queries_node и т.д.), patch.object работает
        # как обычно, т.к. графу подменять нечего.
        with patch.object(agent.nodes, "expand_queries_node", wraps=agent.nodes.expand_queries_node) as spy_expand, \
             patch.object(agent.nodes, "retrieve_multi_node", wraps=agent.nodes.retrieve_multi_node) as spy_retrieve_multi, \
             patch.object(agent.nodes, "personal_search_node", wraps=agent.nodes.personal_search_node) as spy_personal, \
             patch.object(agent.nodes, "resolve_docs_node", wraps=agent.nodes.resolve_docs_node) as spy_resolve_docs, \
             patch.object(agent.nodes, "gather_passports_node", wraps=agent.nodes.gather_passports_node) as spy_passports, \
             patch.object(agent.nodes, "no_data_node", wraps=agent.nodes.no_data_node) as spy_no_data, \
             patch.object(agent.nodes, "reflect_node", wraps=agent.nodes.reflect_node) as spy_reflect, \
             patch.object(agent.nodes, "post_actions_node", wraps=agent.nodes.post_actions_node) as spy_post_actions:
            final_state = await agent.app.ainvoke(inputs)

        spy_expand.assert_not_called()
        spy_retrieve_multi.assert_not_called()
        spy_personal.assert_not_called()
        spy_resolve_docs.assert_not_called()
        spy_passports.assert_not_called()
        spy_no_data.assert_not_called()
        spy_reflect.assert_not_called()
        spy_post_actions.assert_not_called()

        # plan_node/execute_subtasks_node реально отработали - проверяем по эффектам:
        # generate_json_raw вызван (только plan_node его зовёт на этом пути), и ответ
        # получен (граф дошёл до generate/END, значит execute_subtasks отработал).
        agent.llm_provider.generate_json_raw.assert_called_once()
        assert final_state["response_model"]


class TestRunStreamParity:
    @pytest.mark.asyncio
    async def test_domain_rag_event_sequence_unchanged_and_new_nodes_invoked(self):
        item = make_retrieve_item()
        agent = make_agent(retrieval_items=[item])

        async def fake_generate_stream(*, current_query, data_prompt):
            yield "ответ"

        agent.llm_provider.generate_stream = fake_generate_stream

        # run_stream() с 2026-08-05 (StreamRunner удалён) гоняет ТОТ ЖЕ скомпилированный
        # граф (agent.app.astream), что и run() - LangGraph захватывает bound-методы нод
        # в момент build_agent_graph() (в __init__.py, до этого места), так что
        # patch.object(agent.nodes, "rerank_node", ...) постфактум узел графа больше не
        # подменяет (тот же caveat, что уже задокументирован в
        # TestFullGraphByteForByteRegression::test_full_graph_never_touches_disabled_router_nodes) -
        # проверяем по наблюдаемым эффектам вместо spy-вызовов: rerank_node реально
        # отработал, если дошло до сетевого вызова реранкера; extract_sources_node - если
        # финальное "sources"-событие несёт реально найденный item.
        events = [e async for e in agent.run_stream(query="вопрос", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "status", "token", "sources", "done"]
        agent.reranker_service.rerank.assert_awaited_once()
        sources_event = next(e for e in events if e["event"] == "sources")
        assert len(sources_event["data"]["sources"]) == 1
        assert sources_event["data"]["sources"][0]["doc_id"] == item.metadata.doc_id
        # score 0.99 (не исходные 0.9 у item) - подтверждает, что рерос отработал по-настоящему
        # (make_agent по умолчанию мокает reranker на identity-порядок со скором 0.99).
        assert sources_event["data"]["sources"][0]["score"] == 0.99

    @pytest.mark.asyncio
    async def test_smalltalk_like_empty_plan_event_sequence(self):
        agent = make_agent(plan_response=_EMPTY_PLAN_RESPONSE)

        async def fake_generate_stream(*, current_query, data_prompt):
            yield "привет"

        agent.llm_provider.generate_stream = fake_generate_stream

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]
        assert [e["event"] for e in events] == ["status", "status", "token", "sources", "done"]

    @pytest.mark.asyncio
    async def test_run_stream_no_longer_raises_not_implemented_for_any_route(self):
        # Регрессия наоборот: раньше run_stream() кидал NotImplementedError, если
        # state.route оказывался personal/complex (ML-роутер их не мог вернуть живьём,
        # guard был на всякий случай). ML-роутер отключён от графа, а с 2026-08-06
        # query_router удалён совсем - run_stream() строит state.route="domain_rag" по
        # построению (см. run_stream), guard и его исключение убраны как мёртвый код.
        agent = make_agent()
        events = [e async for e in agent.run_stream(query="что-то", history_messages_db=[])]
        assert events[-1]["event"] == "done"

    @pytest.mark.asyncio
    async def test_domain_rag_no_data_short_circuits_without_calling_llm(self):
        # Регрессия: decide_after_rerank/no_data теперь реальны (см. rerank_node) - без
        # этой ветки в run_stream() SSE-путь безусловно шёл бы в generate() даже при
        # пустом/слабом retrieval, расходясь с /llm/answer (компилированный граф),
        # который корректно обрывается в no_data.
        item = make_retrieve_item()

        async def low_score_rerank(*, query, texts):
            return [{"index": 0, "score": 0.1}]  # ниже rerank_no_data_threshold (0.35)

        agent = make_agent(retrieval_items=[item], reranker_side_effect=low_score_rerank)

        events = [e async for e in agent.run_stream(query="вопрос без ответа в базе", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "status", "token", "sources", "done"]
        assert events[-1]["data"]["answer"]
        assert "нет информации" in events[-1]["data"]["answer"]
        agent.llm_provider.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_need_more_loops_back_to_search_and_reaches_generate(self):
        # Живой сценарий, который просил пользователь: первая попытка слабая, reflect
        # просит уточняющий поиск с новой формулировкой, второй заход находит хорошо -
        # и ответ строится по нему, не обрываясь в no_data после первой неудачи.
        weak_item = make_retrieve_item(parent_chunk="слабый результат")
        good_item = make_retrieve_item(parent_chunk="хороший результат")

        call_count = {"rerank": 0}

        async def low_then_high_rerank(*, query, texts):
            call_count["rerank"] += 1
            score = 0.1 if call_count["rerank"] == 1 else 0.99
            return [{"index": 0, "score": score}]

        agent = make_agent(
            reflect_response='{"verdict": "need_more", "new_queries": ["уточнённый запрос"]}',
            reranker_side_effect=low_then_high_rerank,
        )
        agent.retrieval_service.retrieve = AsyncMock(
            side_effect=[
                RetrievalResult(items=[weak_item], total=1),
                RetrievalResult(items=[good_item], total=1),
            ]
        )

        async def fake_generate_stream(*, current_query, data_prompt):
            yield "ответ"

        agent.llm_provider.generate_stream = fake_generate_stream

        events = [e async for e in agent.run_stream(query="вопрос", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "status", "status", "token", "sources", "done"]
        assert agent.retrieval_service.retrieve.await_count == 2
        second_call_queries = agent.retrieval_service.retrieve.await_args_list[1].args[0]
        assert second_call_queries == ["уточнённый запрос"]
        assert events[-1]["data"]["answer"] == "ответ"