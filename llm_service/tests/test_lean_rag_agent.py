from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm_service.application.lean_rag_agent import LeanRagAgent
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

def make_agent(
    route: str = "domain_rag",
    llm_answer: str = "финальный ответ",
    expand_response: str = "вариант1\nвариант2",
    retrieval_items: list[RetrieveItem] | None = None,
    reranker_side_effect=None,
) -> LeanRagAgent:
    llm_provider = MagicMock()
    llm_provider.generate = AsyncMock(return_value=llm_answer)
    llm_provider.generate_general = AsyncMock(return_value=expand_response)

    query_router = MagicMock()
    query_router.route = MagicMock(return_value=route)

    retrieval_service = MagicMock()
    retrieval_service.retrieve = AsyncMock(
        return_value=RetrievalResult(items=retrieval_items or [], total=len(retrieval_items or []))
    )

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
        query_router=query_router,
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
# route_node
# ---------------------------------------------------------------------------

class TestRouteNode:
    @pytest.mark.asyncio
    async def test_writes_route_to_state(self):
        agent = make_agent(route="domain_rag")
        result = await agent.route_node(make_state(query="что такое редуктор?"))
        assert result == {"route": "domain_rag"}

    @pytest.mark.asyncio
    async def test_calls_router_with_query(self):
        agent = make_agent()
        await agent.route_node(make_state(query="привет"))
        agent.query_router.route.assert_called_once_with("привет")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("route", ["smalltalk", "out_of_domain", "domain_rag"])
    async def test_all_routes_passed_through(self, route: str):
        agent = make_agent(route=route)
        result = await agent.route_node(make_state())
        assert result["route"] == route


# ---------------------------------------------------------------------------
# decide_after_router
# ---------------------------------------------------------------------------

class TestDecideAfterRouter:
    @pytest.mark.asyncio
    async def test_smalltalk_returns_smalltalk(self):
        agent = make_agent()
        result = await agent.decide_after_router(make_state(route="smalltalk"))
        assert result == "smalltalk"

    @pytest.mark.asyncio
    async def test_out_of_domain_returns_out_of_domain(self):
        agent = make_agent()
        result = await agent.decide_after_router(make_state(route="out_of_domain"))
        assert result == "out_of_domain"

    @pytest.mark.asyncio
    async def test_domain_rag_goes_to_expand_queries(self):
        agent = make_agent()
        result = await agent.decide_after_router(make_state(route="domain_rag"))
        assert result == "expand_queries"


# ---------------------------------------------------------------------------
# expand_queries_node
# ---------------------------------------------------------------------------

class TestExpandQueriesNode:
    @pytest.mark.asyncio
    async def test_original_query_always_in_result(self):
        agent = make_agent(expand_response="вариант1\nвариант2")
        result = await agent.expand_queries_node(make_state(query="исходный запрос"))
        assert "исходный запрос" in result["expanded_queries"]

    @pytest.mark.asyncio
    async def test_llm_variants_added_to_queries(self):
        agent = make_agent(expand_response="вариант1\nвариант2")
        result = await agent.expand_queries_node(make_state(query="исходный"))
        assert "вариант1" in result["expanded_queries"]
        assert "вариант2" in result["expanded_queries"]

    @pytest.mark.asyncio
    async def test_calls_llm_generate_general(self):
        agent = make_agent()
        await agent.expand_queries_node(make_state())
        agent.llm_provider.generate_general.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_duplicates_in_result(self):
        agent = make_agent(expand_response="тестовый запрос\nвариант2")
        result = await agent.expand_queries_node(make_state(query="тестовый запрос"))
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
        await agent.expand_queries_node(state)
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
        result = await agent.retrieve_multi_node(make_state(expanded_queries=["q"]))
        assert result["retrieval_data"] == [item]

    @pytest.mark.asyncio
    async def test_passes_expanded_queries_to_service(self):
        agent = make_agent()
        queries = ["запрос1", "запрос2", "запрос3"]
        await agent.retrieve_multi_node(make_state(expanded_queries=queries))
        agent.retrieval_service.retrieve.assert_called_once_with(queries)

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_list(self):
        agent = make_agent(retrieval_items=[])
        result = await agent.retrieve_multi_node(make_state())
        assert result["retrieval_data"] == []


# ---------------------------------------------------------------------------
# _format_child_chunks_retrive_data
# ---------------------------------------------------------------------------

class TestFormatChildChunks:
    def test_parent_chunk_in_output(self):
        agent = make_agent()
        item = make_retrieve_item(parent_chunk="основной текст раздела")
        assert "основной текст раздела" in agent._format_child_chunks_retrive_data(item)

    def test_document_and_title_in_output(self):
        agent = make_agent()
        item = make_retrieve_item(
            source="СП 4.13130.2013 Ограничение распространения пожара.pdf",
            headers={"chapter_number": "5.2", "title": "5.2 Требования к объектам"},
        )
        result = agent._format_child_chunks_retrive_data(item)
        assert "СП 4.13130.2013 Ограничение распространения пожара.pdf" in result
        assert "5.2 Требования к объектам" in result

    def test_no_python_dict_repr_in_output(self):
        """Регрессия: раньше в промпт шёл сырой repr headers, напр. "{'chapter_number': '2', ...}"."""
        agent = make_agent()
        item = make_retrieve_item()
        result = agent._format_child_chunks_retrive_data(item)
        assert "{'" not in result
        assert "score" not in result.lower()

    def test_missing_title_falls_back_gracefully(self):
        agent = make_agent()
        item = make_retrieve_item(headers={})
        result = agent._format_child_chunks_retrive_data(item)
        assert "без названия" in result

    def test_empty_children_no_crash(self):
        agent = make_agent()
        item = RetrieveItem(
            parent_chunk="текст",
            child_chunks=[],
            metadata=RetrieveItemMetadata(doc_id="d", parent_id="p", score=0.9),
        )
        result = agent._format_child_chunks_retrive_data(item)
        assert "текст" in result


# ---------------------------------------------------------------------------
# build_prompt_node
# ---------------------------------------------------------------------------

class TestBuildPromptNode:
    @pytest.mark.asyncio
    async def test_returns_final_context(self):
        agent = make_agent()
        result = await agent.build_prompt_node(make_state())
        assert "final_context" in result
        assert isinstance(result["final_context"], FinalPromptData)

    @pytest.mark.asyncio
    async def test_current_query_mapped(self):
        agent = make_agent()
        result = await agent.build_prompt_node(make_state(query="мой вопрос"))
        assert result["final_context"].current_query == "мой вопрос"

    @pytest.mark.asyncio
    async def test_summary_mapped(self):
        agent = make_agent()
        result = await agent.build_prompt_node(make_state(summary="краткое резюме"))
        assert result["final_context"].summary == "краткое резюме"

    @pytest.mark.asyncio
    async def test_retrieval_data_serialized_to_context_str(self):
        agent = make_agent()
        item = make_retrieve_item(parent_chunk="важный раздел документа")
        result = await agent.build_prompt_node(make_state(retrieval_data=[item]))
        assert "важный раздел документа" in result["final_context"].context

    @pytest.mark.asyncio
    async def test_messages_serialized_to_history_str(self):
        agent = make_agent()
        state = make_state(messages=[
            {"role": "user", "content": "привет"},
            {"role": "assistant", "content": "здравствуй"},
        ])
        result = await agent.build_prompt_node(state)
        history = result["final_context"].chat_history
        assert "user: привет" in history
        assert "assistant: здравствуй" in history

    @pytest.mark.asyncio
    async def test_empty_retrieval_gives_empty_context(self):
        agent = make_agent()
        result = await agent.build_prompt_node(make_state(retrieval_data=[]))
        assert result["final_context"].context == ""


# ---------------------------------------------------------------------------
# generate_node
# ---------------------------------------------------------------------------

class TestGenerateNode:
    @pytest.mark.asyncio
    async def test_returns_response_model(self):
        agent = make_agent(llm_answer="готовый ответ")
        final_ctx = FinalPromptData(
            context="контекст", chat_history="история",
            summary="резюме", current_query="вопрос",
        )
        result = await agent.generate_node(make_state(query="вопрос", final_context=final_ctx))
        assert result == {"response_model": "готовый ответ"}

    @pytest.mark.asyncio
    async def test_calls_llm_generate_with_correct_args(self):
        agent = make_agent()
        final_ctx = FinalPromptData(
            context="ctx", chat_history="hist",
            summary="sum", current_query="q",
        )
        state = make_state(query="q", final_context=final_ctx)
        await agent.generate_node(state)
        agent.llm_provider.generate.assert_called_once_with(
            current_query="q",
            data_prompt=final_ctx,
        )

    @pytest.mark.asyncio
    async def test_passes_final_context_not_raw_state(self):
        agent = make_agent()
        final_ctx = FinalPromptData(
            context="специфический контекст", chat_history="",
            summary="", current_query="запрос",
        )
        state = make_state(final_context=final_ctx)
        await agent.generate_node(state)
        call_kwargs = agent.llm_provider.generate.call_args.kwargs
        assert call_kwargs["data_prompt"] is final_ctx


# ---------------------------------------------------------------------------
# run_stream - обрыв соединения с апстрим-LLM не должен терять уже отданные токены
# ---------------------------------------------------------------------------

class TestRunStream:
    @pytest.mark.asyncio
    async def test_yields_tokens_sources_done_on_success(self):
        agent = make_agent(route="smalltalk")

        async def fake_generate_stream(*, current_query, data_prompt):
            yield "Привет"
            yield ", мир"

        agent.llm_provider.generate_stream = fake_generate_stream

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "token", "token", "sources", "done"]
        assert events[-1]["data"]["answer"] == "Привет, мир"

    @pytest.mark.asyncio
    async def test_marks_partial_answer_interrupted_on_mid_stream_failure(self):
        agent = make_agent(route="smalltalk")

        async def fake_generate_stream(*, current_query, data_prompt):
            yield "частичный "
            yield "ответ"
            raise ConnectionError("сеть пропала")

        agent.llm_provider.generate_stream = fake_generate_stream

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]

        # Два реальных токена + один токен-пометка об обрыве, дальше как обычно sources/done -
        # исключение НЕ должно всплыть наружу и оборвать SSE-поток без данных для сохранения.
        assert [e["event"] for e in events] == ["status", "token", "token", "token", "sources", "done"]
        final_answer = events[-1]["data"]["answer"]
        assert final_answer.startswith("частичный ответ")
        assert "прерван" in final_answer

    @pytest.mark.asyncio
    async def test_pause_between_deltas_does_not_break_generation(self):
        # Heartbeat теперь целиком на стороне EventSourceResponse (см. agent_routers.py) -
        # run_stream() больше не оборачивает generate_stream() в свою task/wait-машинерию
        # и сам ничего не пингует, так что тут больше нечего проверять про "ping"; осталась
        # только проверка, что пауза между дельтами (напр. сеть подвисла) не ломает сборку
        # ответа при обычном async for.
        agent = make_agent(route="smalltalk")

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
        agent = make_agent(route="smalltalk", llm_answer="ответ из фолбэка")

        async def fake_generate_stream(*, current_query, data_prompt):
            if False:
                yield ""
            raise ConnectionError("gateway 502")

        agent.llm_provider.generate_stream = fake_generate_stream

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "token", "sources", "done"]
        assert events[1]["data"]["text"] == "ответ из фолбэка"
        assert events[-1]["data"]["answer"] == "ответ из фолбэка"
        agent.llm_provider.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_slow_fallback_still_returns_answer(self):
        # Heartbeat во время fallback тоже теперь на стороне EventSourceResponse (не
        # unit-тестируется на этом уровне - см. интеграционный live-тест в TODO). Здесь
        # проверяем то, что доступно юнит-тестом: медленный fallback всё равно доходит до
        # конца и отдаёт ответ, а не обрывается из-за отсутствия прежней task-обвязки.
        agent = make_agent(route="smalltalk")

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

        assert [e["event"] for e in events] == ["status", "token", "sources", "done"]
        assert events[-1]["data"]["answer"] == "медленный ответ из фолбэка"

    @pytest.mark.asyncio
    async def test_fallback_failure_produces_error_note(self):
        agent = make_agent(route="smalltalk")

        async def fake_generate_stream(*, current_query, data_prompt):
            if False:
                yield ""
            raise ConnectionError("gateway 502")

        agent.llm_provider.generate_stream = fake_generate_stream
        agent.llm_provider.generate = AsyncMock(side_effect=ConnectionError("и обычный вызов тоже упал"))

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "token", "sources", "done"]
        assert "Не удалось получить ответ" in events[-1]["data"]["answer"]

    @pytest.mark.asyncio
    async def test_does_not_fall_back_if_some_tokens_already_shown(self):
        # Отличие от предыдущих двух: тут уже есть частичный ответ - fallback не должен
        # включаться (создал бы вторую, не связанную генерацию поверх показанного текста).
        agent = make_agent(route="smalltalk")

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
        result = await agent.rerank_node(make_state(retrieval_data=[item_a, item_b]))

        reordered = result["retrieval_data"]
        assert [item.parent_chunk for item in reordered] == ["чанк B", "чанк A"]
        assert reordered[0].metadata.score == 0.95
        assert reordered[1].metadata.score == 0.1

    @pytest.mark.asyncio
    async def test_empty_retrieval_skips_network_call(self):
        agent = make_agent()
        result = await agent.rerank_node(make_state(retrieval_data=[]))
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
        await agent.rerank_node(make_state(retrieval_data=[item]))
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
        await agent.rerank_node(make_state(retrieval_data=[item]))
        call_kwargs = agent.reranker_service.rerank.call_args.kwargs
        assert call_kwargs["texts"] == ["только родительский текст"]


class TestDecideAfterRerank:
    @pytest.mark.asyncio
    async def test_empty_retrieval_returns_empty(self):
        agent = make_agent()
        assert await agent.decide_after_rerank(make_state(retrieval_data=[])) == "empty"

    @pytest.mark.asyncio
    async def test_score_below_no_data_threshold_returns_empty(self):
        # Порог из ai_config.toml: rerank_no_data_threshold = 0.35
        agent = make_agent()
        item = make_retrieve_item()
        item.metadata.score = 0.2
        assert await agent.decide_after_rerank(make_state(retrieval_data=[item])) == "empty"

    @pytest.mark.asyncio
    async def test_score_in_grey_zone_returns_grey_zone(self):
        # Между rerank_no_data_threshold (0.35) и rerank_grey_zone_threshold (0.60)
        agent = make_agent()
        item = make_retrieve_item()
        item.metadata.score = 0.5
        assert await agent.decide_after_rerank(make_state(retrieval_data=[item])) == "grey_zone"

    @pytest.mark.asyncio
    async def test_score_above_grey_zone_returns_sufficient(self):
        agent = make_agent()
        item = make_retrieve_item()
        item.metadata.score = 0.9
        assert await agent.decide_after_rerank(make_state(retrieval_data=[item])) == "sufficient"


class TestNoDataNode:
    @pytest.mark.asyncio
    async def test_returns_honest_refusal_without_calling_llm(self):
        agent = make_agent()
        result = await agent.no_data_node(make_state())
        assert result["retrieval_empty"] is True
        assert result["response_model"]
        agent.llm_provider.generate.assert_not_called()


# ---------------------------------------------------------------------------
# Остальные новые ноды-заглушки (ARCHITECTURE.md) - детерминированный no-op
# контракт, reflect/personal/plan/... по-прежнему не реализованы.
# ---------------------------------------------------------------------------

class TestNewStubNodesAreInert:
    @pytest.mark.asyncio
    async def test_decide_after_reflect_always_sufficient(self):
        agent = make_agent()
        assert await agent.decide_after_reflect(make_state()) == "sufficient"

    @pytest.mark.asyncio
    async def test_resolve_docs_node_returns_empty(self):
        agent = make_agent()
        assert await agent.resolve_docs_node(make_state()) == {"resolved_docs": []}

    @pytest.mark.asyncio
    async def test_personal_search_node_returns_empty_retrieval(self):
        agent = make_agent()
        assert await agent.personal_search_node(make_state()) == {"retrieval_data": []}

    @pytest.mark.asyncio
    async def test_gather_passports_node_returns_empty(self):
        agent = make_agent()
        assert await agent.gather_passports_node(make_state()) == {"document_passports": []}

    @pytest.mark.asyncio
    async def test_plan_node_returns_empty_plan(self):
        agent = make_agent()
        result = await agent.plan_node(make_state())
        assert result["plan"] == PlanOutput(subtasks=[], synthesis="")

    @pytest.mark.asyncio
    async def test_post_actions_node_never_produces_action(self):
        agent = make_agent()
        assert await agent.post_actions_node(make_state()) == {"proposed_action": None}


class TestDecideAfterResolveDocs:
    @pytest.mark.asyncio
    async def test_zero_docs_goes_to_clarify(self):
        agent = make_agent()
        assert await agent.decide_after_resolve_docs(make_state(resolved_docs=[])) == "clarify"

    @pytest.mark.asyncio
    async def test_over_threshold_goes_to_background(self):
        agent = make_agent()
        many_docs = [f"doc-{i}" for i in range(10)]
        assert await agent.decide_after_resolve_docs(make_state(resolved_docs=many_docs)) == "background"

    @pytest.mark.asyncio
    async def test_within_threshold_goes_to_gather_passports(self):
        agent = make_agent()
        docs = ["doc-1", "doc-2"]
        assert await agent.decide_after_resolve_docs(make_state(resolved_docs=docs)) == "gather_passports"


class TestExecuteSubtasksNode:
    @pytest.mark.asyncio
    async def test_dispatches_read_tool_and_collects_result(self):
        item = make_retrieve_item()
        agent = make_agent(retrieval_items=[item])
        plan = PlanOutput(subtasks=[PlanSubtask(tool="search_docs", args={"query": "test"})])
        result = await agent.execute_subtasks_node(make_state(plan=plan))
        assert len(result["subtask_results"]) == 1
        assert result["subtask_results"][0]["tool"] == "search_docs"

    @pytest.mark.asyncio
    async def test_refuses_write_tool(self):
        # Регрессия ARCHITECTURE.md §8 Excessive Agency: даже если plan когда-нибудь
        # ошибочно предложит write-инструмент, диспетчер не должен его исполнять.
        agent = make_agent()
        plan = PlanOutput(subtasks=[PlanSubtask(tool="create_note", args={"title": "t", "content": "c"})])
        result = await agent.execute_subtasks_node(make_state(plan=plan))
        assert result["subtask_results"] == []

    @pytest.mark.asyncio
    async def test_unknown_tool_skipped_not_raised(self):
        agent = make_agent()
        plan = PlanOutput(subtasks=[PlanSubtask(tool="not_a_real_tool", args={})])
        result = await agent.execute_subtasks_node(make_state(plan=plan))
        assert result["subtask_results"] == []

    @pytest.mark.asyncio
    async def test_no_plan_returns_empty_results(self):
        agent = make_agent()
        result = await agent.execute_subtasks_node(make_state(plan=None))
        assert result["subtask_results"] == []


class TestDecideAfterExecuteSubtasks:
    @pytest.mark.asyncio
    async def test_search_docs_result_routes_to_rerank(self):
        agent = make_agent()
        state = make_state(subtask_results=[{"tool": "search_docs", "result": {}}])
        assert await agent.decide_after_execute_subtasks(state) == "rerank"

    @pytest.mark.asyncio
    async def test_no_search_docs_routes_to_build_prompt(self):
        agent = make_agent()
        assert await agent.decide_after_execute_subtasks(make_state(subtask_results=[])) == "build_prompt"


class TestDecideAfterRouterNewClasses:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("route", ["personal", "complex"])
    async def test_new_routes_pass_through(self, route):
        # Через make_state напрямую, минуя мок роутера - доказывает корректность
        # маршрутизации графа даже притом, что MLQueryRouter физически не может
        # вернуть эти классы сегодня (нет обучающих примеров).
        agent = make_agent()
        result = await agent.decide_after_router(make_state(route=route))
        assert result == route


class TestExtractSourcesNode:
    @pytest.mark.asyncio
    async def test_matches_build_sources_output(self):
        agent = make_agent()
        item = make_retrieve_item()
        result = await agent.extract_sources_node(make_state(retrieval_data=[item]))
        assert result["sources"] == LeanRagAgent.build_sources([item])


class TestDecideAfterGenerate:
    @pytest.mark.asyncio
    async def test_smalltalk_always_ends_even_with_marker(self):
        agent = make_agent()
        state = make_state(route="smalltalk", query="сохрани это")
        assert await agent.decide_after_generate(state) == "end"

    @pytest.mark.asyncio
    async def test_domain_rag_without_marker_ends(self):
        agent = make_agent()
        state = make_state(route="domain_rag", query="что такое редуктор?")
        assert await agent.decide_after_generate(state) == "end"

    @pytest.mark.asyncio
    async def test_domain_rag_with_marker_goes_to_post_actions(self):
        agent = make_agent()
        state = make_state(route="domain_rag", query="сохрани это в заметку")
        assert await agent.decide_after_generate(state) == "post_actions"


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
        agent = make_agent(route="domain_rag", llm_answer="итоговый ответ", retrieval_items=[item])

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
    @pytest.mark.parametrize("route", ["domain_rag", "smalltalk", "out_of_domain"])
    async def test_full_graph_never_touches_scaffolding_nodes(self, route):
        item = make_retrieve_item()
        agent = make_agent(route=route, retrieval_items=[item])
        inputs = LeanAgentState(
            query="вопрос", messages=[], summary="", route=route, expanded_queries=["вопрос"],
        )

        with patch.object(agent, "no_data_node", wraps=agent.no_data_node) as spy_no_data, \
             patch.object(agent, "reflect_node", wraps=agent.reflect_node) as spy_reflect, \
             patch.object(agent, "post_actions_node", wraps=agent.post_actions_node) as spy_post_actions, \
             patch.object(agent, "resolve_docs_node", wraps=agent.resolve_docs_node) as spy_resolve_docs, \
             patch.object(agent, "plan_node", wraps=agent.plan_node) as spy_plan:
            await agent.app.ainvoke(inputs)

        spy_no_data.assert_not_called()
        spy_reflect.assert_not_called()
        spy_post_actions.assert_not_called()
        spy_resolve_docs.assert_not_called()
        spy_plan.assert_not_called()


class TestRunStreamParity:
    @pytest.mark.asyncio
    async def test_domain_rag_event_sequence_unchanged_and_new_nodes_invoked(self):
        item = make_retrieve_item()
        agent = make_agent(route="domain_rag", retrieval_items=[item])

        async def fake_generate_stream(*, current_query, data_prompt):
            yield "ответ"

        agent.llm_provider.generate_stream = fake_generate_stream

        with patch.object(agent, "rerank_node", wraps=agent.rerank_node) as spy_rerank, \
             patch.object(agent, "extract_sources_node", wraps=agent.extract_sources_node) as spy_extract:
            events = [e async for e in agent.run_stream(query="вопрос", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "status", "status", "token", "sources", "done"]
        spy_rerank.assert_awaited_once()
        spy_extract.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_smalltalk_event_sequence_unchanged(self):
        agent = make_agent(route="smalltalk")

        async def fake_generate_stream(*, current_query, data_prompt):
            yield "привет"

        agent.llm_provider.generate_stream = fake_generate_stream

        events = [e async for e in agent.run_stream(query="привет", history_messages_db=[])]
        assert [e["event"] for e in events] == ["status", "token", "sources", "done"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("route", ["personal", "complex"])
    async def test_unreachable_route_raises_not_implemented_not_silently_mishandled(self, route):
        agent = make_agent(route=route)
        with pytest.raises(NotImplementedError):
            async for _ in agent.run_stream(query="что-то", history_messages_db=[]):
                pass

    @pytest.mark.asyncio
    async def test_domain_rag_no_data_short_circuits_without_calling_llm(self):
        # Регрессия: decide_after_rerank/no_data теперь реальны (см. rerank_node) - без
        # этой ветки в run_stream() SSE-путь безусловно шёл бы в generate() даже при
        # пустом/слабом retrieval, расходясь с /llm/answer (компилированный граф),
        # который корректно обрывается в no_data.
        item = make_retrieve_item()

        async def low_score_rerank(*, query, texts):
            return [{"index": 0, "score": 0.1}]  # ниже rerank_no_data_threshold (0.35)

        agent = make_agent(route="domain_rag", retrieval_items=[item], reranker_side_effect=low_score_rerank)

        events = [e async for e in agent.run_stream(query="вопрос без ответа в базе", history_messages_db=[])]

        assert [e["event"] for e in events] == ["status", "status", "status", "token", "sources", "done"]
        assert events[-1]["data"]["answer"]
        assert "нет информации" in events[-1]["data"]["answer"]
        agent.llm_provider.generate.assert_not_called()