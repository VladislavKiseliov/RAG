import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_service.domain.exceptions import DocumentAlreadyExists
from rag_service.infrastructures.db.session import create_engine, create_session_factory
from rag_service.infrastructures.repositories.document_repository import DocumentRepository
from rag_service.models import DocumentStatus, Documents, ParentChunks
from rag_service.settings import settings


pytestmark = pytest.mark.asyncio(loop_scope="module")

engine = create_engine(settings.rag_database_url)
session_factory: async_sessionmaker[AsyncSession] = create_session_factory(engine)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def repo() -> DocumentRepository:
    return DocumentRepository(session_factory)


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def created_doc_ids() -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    yield ids
    if not ids:
        return

    async with session_factory() as session:
        await session.execute(delete(Documents).where(Documents.id.in_(ids)))
        await session.commit()


@pytest_asyncio.fixture(scope="module", autouse=True, loop_scope="module")
async def dispose_engine() -> None:
    yield
    await engine.dispose()


async def _create_document(
    repo: DocumentRepository,
    created_doc_ids: list[uuid.UUID],
    *,
    filename: str = "test-doc",
) -> tuple[uuid.UUID, str]:
    file_hash = f"test-hash-{uuid.uuid4()}"
    doc_id = await repo.create_document(filename=filename, file_hash=file_hash, meta={"source": "test"})
    created_doc_ids.append(doc_id)
    return doc_id, file_hash


async def test_create_doc_persists_document(repo: DocumentRepository, created_doc_ids: list[uuid.UUID]) -> None:
    document_id, file_hash = await _create_document(repo, created_doc_ids, filename="test")

    document = await repo.get_document_by_id(document_id)

    assert document is not None
    assert document.filename == "test"
    assert document.file_hash == file_hash
    assert document.status == DocumentStatus.processing


async def test_get_document_by_hash_returns_document(repo: DocumentRepository, created_doc_ids: list[uuid.UUID]) -> None:
    document_id, file_hash = await _create_document(repo, created_doc_ids)

    document = await repo.get_document_by_hash(file_hash)

    assert document is not None
    assert document.id == document_id


async def test_get_document_by_id_returns_none_for_missing_document(repo: DocumentRepository) -> None:
    document = await repo.get_document_by_id(uuid.uuid4())

    assert document is None


async def test_create_document_raises_for_duplicate_hash(repo: DocumentRepository, created_doc_ids: list[uuid.UUID]) -> None:
    _, file_hash = await _create_document(repo, created_doc_ids)

    with pytest.raises(DocumentAlreadyExists):
        await repo.create_document(filename="duplicate", file_hash=file_hash, meta=None)


async def test_list_documents_filters_by_status_and_filename(repo: DocumentRepository, created_doc_ids: list[uuid.UUID]) -> None:
    matching_id, _ = await _create_document(repo, created_doc_ids, filename="pump-manual")
    other_id, _ = await _create_document(repo, created_doc_ids, filename="valve-manual")
    await repo.set_status(other_id, DocumentStatus.completed, chunk_count=3)

    documents = await repo.list_documents(limit=10, offset=0, status=DocumentStatus.processing.value, filename="pump")

    assert [doc.id for doc in documents] == [matching_id]


async def test_list_documents_filters_by_created_range(repo: DocumentRepository, created_doc_ids: list[uuid.UUID]) -> None:
    old_id, _ = await _create_document(repo, created_doc_ids, filename="old-doc")
    new_id, _ = await _create_document(repo, created_doc_ids, filename="new-doc")

    async with session_factory() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(days=2)
        await session.execute(update(Documents).where(Documents.id == old_id).values(created_at=cutoff))
        await session.commit()

    created_from = datetime.now(timezone.utc) - timedelta(days=1)
    documents = await repo.list_documents(limit=10, offset=0, created_from=created_from)

    document_ids = {doc.id for doc in documents}
    assert new_id in document_ids
    assert old_id not in document_ids


async def test_set_status_updates_status_and_chunk_count(repo: DocumentRepository, created_doc_ids: list[uuid.UUID]) -> None:
    document_id, _ = await _create_document(repo, created_doc_ids)

    await repo.set_status(document_id, DocumentStatus.completed, chunk_count=7)
    document = await repo.get_document_by_id(document_id)

    assert document is not None
    assert document.status == DocumentStatus.completed
    assert document.chunk_count == 7


async def test_delete_document_removes_document_and_chunks(repo: DocumentRepository, created_doc_ids: list[uuid.UUID]) -> None:
    document_id, _ = await _create_document(repo, created_doc_ids)
    parent_id = uuid.uuid4()
    await repo.bulk_insert_chunks(
        document_id,
        [
            {"id": parent_id, "content": "chunk-1", "chunk_index": 0},
            {"content": "chunk-2", "chunk_index": 1},
        ],
    )

    await repo.delete_document(document_id)
    created_doc_ids.remove(document_id)

    document = await repo.get_document_by_id(document_id)
    parents = await repo.get_parents_by_ids([parent_id], doc_id=document_id)

    assert document is None
    assert parents == []

    async with session_factory() as session:
        result = await session.execute(select(func.count()).select_from(ParentChunks).where(ParentChunks.doc_id == document_id))
        assert result.scalar_one() == 0


async def test_get_max_chunk_index_returns_none_without_chunks(repo: DocumentRepository, created_doc_ids: list[uuid.UUID]) -> None:
    document_id, _ = await _create_document(repo, created_doc_ids)

    max_index = await repo.get_max_chunk_index(document_id)

    assert max_index is None


async def test_bulk_insert_chunks_persists_rows_and_get_max_index(repo: DocumentRepository, created_doc_ids: list[uuid.UUID]) -> None:
    document_id, _ = await _create_document(repo, created_doc_ids)
    first_parent_id = uuid.uuid4()
    second_parent_id = uuid.uuid4()

    await repo.bulk_insert_chunks(
        document_id,
        [
            {"id": first_parent_id, "content": "alpha", "page_num": "1", "headers": {"h1": "A"}, "chunk_index": 0},
            {"id": second_parent_id, "content": "beta", "page_num": "2", "headers": {"h1": "B"}, "chunk_index": 1},
        ],
        batch_size=1,
    )

    parents = await repo.get_parents_by_ids([second_parent_id, first_parent_id], doc_id=document_id)
    max_index = await repo.get_max_chunk_index(document_id)

    assert [parent.id for parent in parents] == [first_parent_id, second_parent_id]
    assert [parent.content for parent in parents] == ["alpha", "beta"]
    assert max_index == 1


async def test_get_parents_by_ids_returns_empty_for_empty_input(repo: DocumentRepository) -> None:
    parents = await repo.get_parents_by_ids([])

    assert parents == []


async def test_get_parents_by_ids_can_filter_by_document(repo: DocumentRepository, created_doc_ids: list[uuid.UUID]) -> None:
    first_doc_id, _ = await _create_document(repo, created_doc_ids, filename="first")
    second_doc_id, _ = await _create_document(repo, created_doc_ids, filename="second")
    first_parent_id = uuid.uuid4()
    second_parent_id = uuid.uuid4()

    await repo.bulk_insert_chunks(first_doc_id, [{"id": first_parent_id, "content": "first", "chunk_index": 0}])
    await repo.bulk_insert_chunks(second_doc_id, [{"id": second_parent_id, "content": "second", "chunk_index": 0}])

    parents = await repo.get_parents_by_ids([first_parent_id, second_parent_id], doc_id=first_doc_id)

    assert [parent.id for parent in parents] == [first_parent_id]
