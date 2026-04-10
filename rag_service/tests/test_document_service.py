import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from rag_service.application.document_service import DocumentQueryService, DocumentService
from rag_service.models import DocumentStatus


@pytest.fixture
def service() -> DocumentService:
    return DocumentService(session_factory=SimpleNamespace())


@pytest.fixture
def query_service() -> DocumentQueryService:
    return DocumentQueryService(session_factory=SimpleNamespace())


@pytest.mark.asyncio
async def test_get_document_by_hash_delegates_to_repository(service: DocumentService) -> None:
    expected = object()
    service._repo.get_document_by_hash = AsyncMock(return_value=expected)

    result = await service.get_document_by_hash("hash-1")

    assert result is expected
    service._repo.get_document_by_hash.assert_awaited_once_with("hash-1")


@pytest.mark.asyncio
async def test_create_doc_creates_new_document_with_sanitized_filename(service: DocumentService) -> None:
    doc_id = uuid.uuid4()
    service._repo.get_document_by_hash = AsyncMock(return_value=None)
    service._repo.create_document = AsyncMock(return_value=doc_id)

    result = await service.create_doc("..\\nested/test.pdf", "hash-1", {"a": 1})

    assert result == doc_id
    service._repo.create_document.assert_awaited_once_with("test.pdf", "hash-1", {"a": 1}, doc_id=None)


@pytest.mark.asyncio
async def test_create_doc_returns_existing_completed_document_id(service: DocumentService) -> None:
    existing_id = uuid.uuid4()
    existing = SimpleNamespace(id=existing_id, status=DocumentStatus.completed)
    service._repo.get_document_by_hash = AsyncMock(return_value=existing)
    service._repo.create_document = AsyncMock()

    result = await service.create_doc("doc.pdf", "hash-1")

    assert result == existing_id
    service._repo.create_document.assert_not_called()


@pytest.mark.asyncio
async def test_create_doc_returns_existing_processing_document_id(service: DocumentService) -> None:
    existing_id = uuid.uuid4()
    existing = SimpleNamespace(id=existing_id, status=DocumentStatus.processing)
    service._repo.get_document_by_hash = AsyncMock(return_value=existing)
    service._repo.create_document = AsyncMock()

    result = await service.create_doc("doc.pdf", "hash-1")

    assert result == existing_id
    service._repo.create_document.assert_not_called()


@pytest.mark.asyncio
async def test_create_doc_recreates_document_after_error_status(service: DocumentService) -> None:
    old_id = uuid.uuid4()
    new_id = uuid.uuid4()
    existing = SimpleNamespace(id=old_id, status=DocumentStatus.error)
    service._repo.get_document_by_hash = AsyncMock(return_value=existing)
    service._repo.delete_document = AsyncMock()
    service._repo.create_document = AsyncMock(return_value=new_id)

    result = await service.create_doc("doc.pdf", "hash-1", doc_id=new_id)

    assert result == new_id
    service._repo.delete_document.assert_awaited_once_with(old_id)
    service._repo.create_document.assert_awaited_once_with("doc.pdf", "hash-1", None, doc_id=new_id)


@pytest.mark.asyncio
async def test_create_doc_raises_for_invalid_filename(service: DocumentService) -> None:
    service._repo.get_document_by_hash = AsyncMock()
    service._repo.create_document = AsyncMock()

    with pytest.raises(ValueError, match="Invalid filename"):
        await service.create_doc("..", "hash-1")

    service._repo.get_document_by_hash.assert_not_called()
    service._repo.create_document.assert_not_called()


@pytest.mark.asyncio
async def test_add_parent_chunks_skips_empty_input(service: DocumentService) -> None:
    service._repo.get_max_chunk_index = AsyncMock()
    service._repo.bulk_insert_chunks = AsyncMock()

    await service.add_parent_chunks(uuid.uuid4(), [])

    service._repo.get_max_chunk_index.assert_not_called()
    service._repo.bulk_insert_chunks.assert_not_called()


@pytest.mark.asyncio
async def test_add_parent_chunks_builds_rows_from_zero_index(service: DocumentService) -> None:
    doc_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    service._repo.get_max_chunk_index = AsyncMock(return_value=None)
    service._repo.bulk_insert_chunks = AsyncMock()

    await service.add_parent_chunks(
        doc_id,
        [
            {"id": parent_id, "text": "alpha", "page_num": 5, "headers": {"h1": "A"}},
            {"text": "beta"},
        ],
    )

    service._repo.get_max_chunk_index.assert_awaited_once_with(doc_id)
    service._repo.bulk_insert_chunks.assert_awaited_once()
    called_doc_id, rows = service._repo.bulk_insert_chunks.await_args.args
    assert called_doc_id == doc_id
    assert rows[0]["id"] == parent_id
    assert rows[0]["content"] == "alpha"
    assert rows[0]["page_num"] == "5"
    assert rows[0]["headers"] == {"h1": "A"}
    assert rows[0]["chunk_index"] == 0
    assert rows[1]["content"] == "beta"
    assert rows[1]["page_num"] == ""
    assert rows[1]["headers"] == {}
    assert rows[1]["chunk_index"] == 1
    assert isinstance(rows[1]["id"], uuid.UUID)


@pytest.mark.asyncio
async def test_add_parent_chunks_appends_after_existing_max_index(service: DocumentService) -> None:
    doc_id = uuid.uuid4()
    service._repo.get_max_chunk_index = AsyncMock(return_value=4)
    service._repo.bulk_insert_chunks = AsyncMock()

    await service.add_parent_chunks(doc_id, [{"text": "x"}, {"text": "y"}])

    _, rows = service._repo.bulk_insert_chunks.await_args.args
    assert [row["chunk_index"] for row in rows] == [5, 6]


@pytest.mark.asyncio
async def test_set_status_delegates_to_repository(service: DocumentService) -> None:
    doc_id = uuid.uuid4()
    service._repo.set_status = AsyncMock()

    await service.set_status(doc_id, DocumentStatus.completed, chunk_count=7)

    service._repo.set_status.assert_awaited_once_with(doc_id, DocumentStatus.completed, chunk_count=7)


@pytest.mark.asyncio
async def test_delete_document_delegates_to_repository(service: DocumentService) -> None:
    doc_id = uuid.uuid4()
    service._repo.delete_document = AsyncMock()

    await service.delete_document(doc_id)

    service._repo.delete_document.assert_awaited_once_with(doc_id)


@pytest.mark.asyncio
async def test_query_service_get_parent_chunks_delegates_to_repository(query_service: DocumentQueryService) -> None:
    doc_id = uuid.uuid4()
    parent_ids = [uuid.uuid4(), uuid.uuid4()]
    expected = [object()]
    query_service._repo.get_parents_by_ids = AsyncMock(return_value=expected)

    result = await query_service.get_parent_chunks(parent_ids, doc_id=doc_id)

    assert result == expected
    query_service._repo.get_parents_by_ids.assert_awaited_once_with(parent_ids, doc_id=doc_id)
