from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_service.application.lean_rag_agent import LeanRagAgent
from llm_service.application.lean_rag_models import (
    ChildChunk,
    FinalPromptData,
    LeanAgentState,
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

    return LeanRagAgent(
        llm_provider=llm_provider,
        query_router=query_router,
        retrieval_service=retrieval_service,
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