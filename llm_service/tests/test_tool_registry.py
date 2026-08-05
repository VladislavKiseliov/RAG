from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_service.application.lean_rag_models import RetrievalResult, RetrieveItem, RetrieveItemMetadata
from llm_service.tool_registry import build_tool_registry


def make_registry(retrieve_return=None):
    retrieval_service = MagicMock()
    retrieval_service.retrieve = AsyncMock(
        return_value=retrieve_return or RetrievalResult(items=[], total=0)
    )
    retrieval_service.find_document_id_by_code = AsyncMock(return_value=None)
    retrieval_service.get_appendix = AsyncMock(return_value=None)
    retrieval_service.list_documents = AsyncMock(return_value=[])
    return build_tool_registry(retrieval_service=retrieval_service), retrieval_service


ALL_EXPECTED_TOOL_NAMES = {
    "search_docs", "get_appendix", "get_chapter", "get_document_passport", "list_documents",
    "search_notes", "search_tasks", "create_task", "create_note", "update_note",
    "calc_gas", "run_audit",
}


def test_registry_contains_all_expected_tools():
    registry, _ = make_registry()
    assert set(registry.keys()) == ALL_EXPECTED_TOOL_NAMES


@pytest.mark.asyncio
async def test_search_docs_is_real_and_wraps_retrieval_service():
    item = RetrieveItem(
        child_chunks=[],
        parent_chunk="text",
        metadata=RetrieveItemMetadata(doc_id="d1", parent_id="p1", score=0.9),
    )
    registry, retrieval_service = make_registry(RetrievalResult(items=[item], total=1))

    result = await registry["search_docs"].fn(query="test query")

    retrieval_service.retrieve.assert_awaited_once_with(["test query"])
    assert result["total"] == 1
    assert result["items"][0]["metadata"]["doc_id"] == "d1"


@pytest.mark.asyncio
async def test_get_appendix_resolves_doc_id_then_fetches_text():
    registry, retrieval_service = make_registry()
    retrieval_service.find_document_id_by_code = AsyncMock(return_value="doc-42")
    retrieval_service.get_appendix = AsyncMock(return_value="текст приложения А")

    result = await registry["get_appendix"].fn(document_code="СП 1.13130.2020")

    retrieval_service.find_document_id_by_code.assert_awaited_once_with("СП 1.13130.2020")
    retrieval_service.get_appendix.assert_awaited_once_with("doc-42")
    assert result == {"text": "текст приложения А", "doc_id": "doc-42"}


@pytest.mark.asyncio
async def test_get_appendix_document_not_found_skips_fetch():
    registry, retrieval_service = make_registry()
    retrieval_service.find_document_id_by_code = AsyncMock(return_value=None)

    result = await registry["get_appendix"].fn(document_code="неизвестный документ")

    retrieval_service.get_appendix.assert_not_called()
    assert result == {"text": None, "doc_id": None}


@pytest.mark.asyncio
async def test_list_documents_returns_registry_contents():
    registry, retrieval_service = make_registry()
    docs = [{"doc_id": "d1", "filename": "СП 1.13130.pdf"}, {"doc_id": "d2", "filename": "ГОСТ 12.pdf"}]
    retrieval_service.list_documents = AsyncMock(return_value=docs)

    result = await registry["list_documents"].fn()

    assert result == {"documents": docs, "total": 2}


@pytest.mark.parametrize("tool_name", sorted(ALL_EXPECTED_TOOL_NAMES - {"search_docs", "get_appendix", "list_documents"}))
@pytest.mark.asyncio
async def test_unimplemented_tools_raise_not_implemented(tool_name):
    # Регрессия: заглушка должна громко падать, а не молча возвращать "успех" -
    # иначе будущий вызывающий код может принять пустой результат за реальный ответ.
    registry, _ = make_registry()
    with pytest.raises(NotImplementedError, match=tool_name):
        await registry[tool_name].fn()


def test_write_tools_are_marked_write_access():
    registry, _ = make_registry()
    write_tools = {"create_task", "create_note", "update_note", "run_audit"}
    for name, tool in registry.items():
        expected_access = "write" if name in write_tools else "read"
        assert tool.access == expected_access, f"{name} should be access={expected_access!r}"


def test_search_docs_args_schema_validates():
    registry, _ = make_registry()
    args = registry["search_docs"].args_schema(query="hello", doc_filter=None)
    assert args.query == "hello"
