from __future__ import annotations

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