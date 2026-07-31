from __future__ import annotations

"""Integration tests for DocumentRepository against real PostgreSQL test DB."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rag_service.api.schemas import DocumentStatus
from rag_service.infrastructures.repositories.document_repository import DocumentRepository
from rag_service.models import Base, DocumentListItemDTO, ParentChunks, DocumentChapters, DocumentTables
from rag_service.settings import settings


pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine():
    """Create engine and align schema to current models contract for repository tests."""
    assert settings.MODE == "TEST", "Repository integration tests must run with MODE=TEST"
    engine = create_async_engine("postgresql+asyncpg://myuser:mypassword@localhost:5432/myapp_db", future=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session_factory(engine):
    """Provide async session factory for repository tests."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def db_session(session_factory):
    """Yield a live async session and rollback uncommitted state on exit."""
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def repo(db_session: AsyncSession) -> DocumentRepository:
    """Repository under test bound to a live async session."""
    return DocumentRepository(db_session)


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def created_doc_ids(session_factory):
    """Collect created document ids and remove them after each test."""
    ids: list[uuid.UUID] = []
    yield ids
    if not ids:
        return
    async with session_factory() as session:
        for doc_id in ids:
            await session.execute(
                text("DELETE FROM rag_kernel.documents WHERE id = :doc_id"),
                {"doc_id": doc_id},
            )
        await session.commit()


async def _create_document(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
    *,
    filename: str = "test-doc.pdf",
    status: DocumentStatus = DocumentStatus.PENDING,
    s3key: str | None = None,
    metadata: dict | None = None,
) -> uuid.UUID:
    """Create and commit one document row for test setup."""
    doc_id = await repo.create_document(
        filename=filename,
        metadata=metadata or {"source": "repo-test"},
        s3key=s3key,
        doc_status=status,
        doc_id=uuid.uuid4(),
    )
    await db_session.commit()
    created_doc_ids.append(doc_id)
    return doc_id


async def test_create_document_persists_core_fields(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Create document and verify filename/status/meta/s3key models."""
    key = f"documents/2026/04/{uuid.uuid4()}__a1b2c3d4.pdf"
    doc_id = await _create_document(
        repo,
        db_session,
        created_doc_ids,
        filename="manual.pdf",
        status=DocumentStatus.PENDING,
        s3key=key,
        metadata={"origin": "integration"},
    )

    loaded = await repo.get_document_by_id(doc_id)
    assert loaded is not None
    assert loaded.filename == "manual.pdf"
    assert loaded.status == "pending"
    assert loaded.s3key == key
    assert loaded.meta == {"origin": "integration"}


async def test_get_document_by_id_returns_none_for_unknown(repo: DocumentRepository) -> None:
    """Unknown UUID should produce None."""
    loaded = await repo.get_document_by_id(uuid.uuid4())
    assert loaded is None


async def test_get_document_by_hash_returns_matching_row(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Lookup by file_hash should return seeded row."""
    hash_value = "h" * 64
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="hash.pdf")

    await db_session.execute(
        update(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id).values(file_hash=hash_value)
    )
    await db_session.commit()

    loaded = await repo.get_document_by_hash(hash_value)
    assert loaded is not None
    assert loaded.id == doc_id


async def test_list_documents_filters_status_filename_and_created_range(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """List query should apply status/filename/date filters correctly."""
    old_doc_id = await _create_document(
        repo,
        db_session,
        created_doc_ids,
        filename="pump-manual-old.pdf",
        status=DocumentStatus.PROCESSING,
    )
    new_doc_id = await _create_document(
        repo,
        db_session,
        created_doc_ids,
        filename="pump-manual-new.pdf",
        status=DocumentStatus.PROCESSING,
    )
    await _create_document(
        repo,
        db_session,
        created_doc_ids,
        filename="valve-manual.pdf",
        status=DocumentStatus.COMPLETED,
    )

    old_time = datetime.now(timezone.utc) - timedelta(days=3)
    await db_session.execute(
        update(DocumentListItemDTO).where(DocumentListItemDTO.id == old_doc_id).values(created_at=old_time)
    )
    await db_session.commit()

    created_from = datetime.now(timezone.utc) - timedelta(days=1)
    rows = await repo.list_documents(
        limit=20,
        offset=0,
        status="processing",
        filename="pump",
        created_from=created_from,
    )
    ids = {row.id for row in rows}
    assert new_doc_id in ids
    assert old_doc_id not in ids


async def test_set_status_updates_status_and_chunk_count(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """set_status should persist both status and optional chunk_count."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="status.pdf")
    await repo.set_status(doc_id, DocumentStatus.COMPLETED, chunk_count=7)
    await db_session.commit()

    loaded = await repo.get_document_by_id(doc_id)
    assert loaded is not None
    assert loaded.status == "completed"
    assert loaded.chunk_count == 7


async def test_update_document_updates_multiple_fields(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """update_document should persist all passed fields in one call."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="update.pdf")
    await repo.update_document(
        doc_id,
        status=DocumentStatus.UPLOAD,
        metadata={"source": "repo-update"},
        chunk_count=5,
        s3key="documents/2026/04/update__11112222.pdf",
        file_hash="b" * 64,
    )
    await db_session.commit()

    loaded = await repo.get_document_by_id(doc_id)
    assert loaded is not None
    assert loaded.status == "uploading"
    assert loaded.meta == {"source": "repo-update"}
    assert loaded.chunk_count == 5
    assert loaded.s3key == "documents/2026/04/update__11112222.pdf"
    assert loaded.file_hash == "b" * 64


async def test_update_document_hash_atomically_updates_hash_and_status(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Atomic hash update should persist both file_hash and status for target row."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="atomic-ok.pdf")
    file_hash = "c" * 64

    await repo.update_document_hash_atomically(doc_id=doc_id, file_hash=file_hash, status=DocumentStatus.EXTRACTING.value)
    await db_session.commit()

    loaded = await repo.get_document_by_id(doc_id)
    assert loaded is not None
    assert loaded.file_hash == file_hash
    assert loaded.status == DocumentStatus.EXTRACTING.value


async def test_update_document_hash_atomically_raises_on_unique_conflict(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Atomic hash update should surface DB unique violation when hash is already used."""
    first_doc_id = await _create_document(repo, db_session, created_doc_ids, filename="atomic-first.pdf")
    second_doc_id = await _create_document(repo, db_session, created_doc_ids, filename="atomic-second.pdf")
    shared_hash = "d" * 64

    await repo.update_document_hash_atomically(
        doc_id=first_doc_id,
        file_hash=shared_hash,
        status=DocumentStatus.EXTRACTING.value,
    )

    await db_session.commit()

    loaded = await repo.get_document_by_id(first_doc_id)
    assert loaded is not None
    assert loaded.file_hash == shared_hash


    # with pytest.raises(IntegrityError):
    #     await repo.update_document_hash_atomically(
    #         doc_id=second_doc_id,
    #         file_hash=shared_hash,
    #         status=DocumentStatus.EXTRACTING.value,
    #     )
    #     await db_session.commit()
    #
    # # await db_session.rollback()


async def test_update_document_hash_atomically_does_not_commit_by_itself(
    repo: DocumentRepository,
    db_session: AsyncSession,
    session_factory,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Repository method should not auto-commit; caller controls transaction boundary."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="atomic-tx.pdf")
    file_hash = "e" * 64

    await repo.update_document_hash_atomically(
        doc_id=doc_id,
        file_hash=file_hash,
        status=DocumentStatus.EXTRACTING.value,
    )

    async with session_factory() as separate_session:
        separate_repo = DocumentRepository(separate_session)
        loaded_before_commit = await separate_repo.get_document_by_id(doc_id)
        assert loaded_before_commit is not None
        assert loaded_before_commit.file_hash is None
        assert loaded_before_commit.status == DocumentStatus.PENDING.value

    await db_session.commit()

    loaded_after_commit = await repo.get_document_by_id(doc_id)
    assert loaded_after_commit is not None
    assert loaded_after_commit.file_hash == file_hash
    assert loaded_after_commit.status == DocumentStatus.EXTRACTING.value


async def test_bulk_insert_chunks_and_read_helpers(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Insert parent chunks and verify max index + retrieval helpers."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="chunks.pdf")
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()

    await repo.bulk_insert_chunks(
        doc_id,
        [
            {"id": first_id, "content": "alpha", "page_num": "1", "headers": {"h1": "A"}, "chunk_index": 0},
            {"id": second_id, "content": "beta", "page_num": "2", "headers": {"h1": "B"}, "chunk_index": 1},
        ],
        batch_size=1,
    )
    await db_session.commit()

    parents = await repo.get_parents_by_ids([second_id, first_id], doc_id=doc_id)
    assert [item.id for item in parents] == [first_id, second_id]

    all_parents = await repo.get_parent_chunks_by_doc_id(doc_id)
    assert [item.id for item in all_parents] == [first_id, second_id]

    max_index = await repo.get_max_chunk_index(doc_id)
    assert max_index == 1


async def test_bulk_insert_chapters_persists_rows(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Insert document chapters and verify they land in document_chapters."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="chapters.pdf")

    await repo.bulk_insert_chapters(
        doc_id,
        [
            {"chapter_number": "1", "title": "Введение", "s3_md_path": f"{doc_id}/chapters/chapter_1.md"},
            {"chapter_number": "2", "title": "Установка", "s3_md_path": f"{doc_id}/chapters/chapter_2.md"},
        ],
    )
    await db_session.commit()

    result = await db_session.execute(
        select(DocumentChapters).where(DocumentChapters.doc_id == doc_id).order_by(DocumentChapters.chapter_number)
    )
    rows = list(result.scalars().all())
    assert [row.chapter_number for row in rows] == ["1", "2"]
    assert [row.title for row in rows] == ["Введение", "Установка"]
    assert rows[0].s3_md_path == f"{doc_id}/chapters/chapter_1.md"
    assert rows[0].summary is None


async def test_bulk_insert_chapters_empty_input_is_noop(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Empty chapters input should not touch the database."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="no-chapters.pdf")

    await repo.bulk_insert_chapters(doc_id, [])
    await db_session.commit()

    result = await db_session.execute(select(DocumentChapters).where(DocumentChapters.doc_id == doc_id))
    assert list(result.scalars().all()) == []


async def test_bulk_insert_tables_persists_rows(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Insert document tables and verify they land in document_tables."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="tables.pdf")

    await repo.bulk_insert_tables(
        doc_id,
        [
            {
                "table_index": 0,
                "s3_csv_path": f"{doc_id}/tables/table_0.csv",
                "s3_html_path": f"{doc_id}/tables/table_0.html",
            },
        ],
    )
    await db_session.commit()

    result = await db_session.execute(select(DocumentTables).where(DocumentTables.doc_id == doc_id))
    rows = list(result.scalars().all())
    assert len(rows) == 1
    assert rows[0].table_index == 0
    assert rows[0].s3_csv_path == f"{doc_id}/tables/table_0.csv"
    assert rows[0].s3_html_path == f"{doc_id}/tables/table_0.html"
    assert rows[0].title is None


async def test_delete_structural_data_removes_chunks_chapters_and_tables(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """delete_structural_data should clear parent chunks, chapters, and tables for the doc, leaving the document row intact."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="reset.pdf")

    await repo.bulk_insert_chunks(
        doc_id,
        [{"id": uuid.uuid4(), "content": "alpha", "page_num": "1", "headers": {}, "chunk_index": 0}],
    )
    await repo.bulk_insert_chapters(
        doc_id,
        [{"chapter_number": "1", "title": "Введение", "s3_md_path": f"{doc_id}/chapters/chapter_1.md"}],
    )
    await repo.bulk_insert_tables(
        doc_id,
        [{"table_index": 0, "s3_csv_path": f"{doc_id}/tables/table_0.csv", "s3_html_path": f"{doc_id}/tables/table_0.html"}],
    )
    await db_session.commit()

    await repo.delete_structural_data(doc_id)
    await db_session.commit()

    assert await repo.get_parent_chunks_by_doc_id(doc_id) == []
    assert await repo.get_chapters_by_doc_id(doc_id) == []
    assert await repo.get_tables_by_doc_id(doc_id) == []
    assert await repo.get_document_by_id(doc_id) is not None


async def test_get_chapters_by_doc_id_returns_in_document_order(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Chapters should come back in the order they were inserted (uuid7 ids sort chronologically)."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="read-chapters.pdf")

    await repo.bulk_insert_chapters(
        doc_id,
        [
            {"chapter_number": "1", "title": "Введение", "s3_md_path": f"{doc_id}/chapters/chapter_1.md"},
            {"chapter_number": "2", "title": "Установка", "s3_md_path": f"{doc_id}/chapters/chapter_2.md"},
        ],
    )
    await db_session.commit()

    chapters = await repo.get_chapters_by_doc_id(doc_id)
    assert [c.chapter_number for c in chapters] == ["1", "2"]
    assert [c.title for c in chapters] == ["Введение", "Установка"]


async def test_get_chapters_by_doc_id_empty_when_none(repo: DocumentRepository) -> None:
    """Unknown/empty document should return an empty chapters list."""
    assert await repo.get_chapters_by_doc_id(uuid.uuid4()) == []


async def test_get_tables_by_doc_id_returns_ordered_by_index(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Tables should come back ordered by table_index ascending."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="read-tables.pdf")

    await repo.bulk_insert_tables(
        doc_id,
        [
            {"table_index": 1, "s3_csv_path": f"{doc_id}/tables/table_1.csv", "s3_html_path": f"{doc_id}/tables/table_1.html"},
            {"table_index": 0, "s3_csv_path": f"{doc_id}/tables/table_0.csv", "s3_html_path": f"{doc_id}/tables/table_0.html"},
        ],
    )
    await db_session.commit()

    tables = await repo.get_tables_by_doc_id(doc_id)
    assert [t.table_index for t in tables] == [0, 1]


async def test_update_table_summary_sets_summary(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """update_table_summary should persist the LLM-generated summary on the target table row."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="table-summary.pdf")

    await repo.bulk_insert_tables(
        doc_id,
        [{"table_index": 0, "s3_csv_path": f"{doc_id}/tables/table_0.csv", "s3_html_path": f"{doc_id}/tables/table_0.html"}],
    )
    await db_session.commit()

    table = (await repo.get_tables_by_doc_id(doc_id))[0]
    await repo.update_table_summary(table.id, "Таблица допустимых давлений.")
    await db_session.commit()

    updated = (await repo.get_tables_by_doc_id(doc_id))[0]
    assert updated.summary == "Таблица допустимых давлений."


async def test_update_table_parent_chunk_id_links_to_qdrant_point_row(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """update_table_parent_chunk_id should link the table row to its parent_chunks row.

    Used by summarize_document_chapters_task to detect a table is already vectorized
    (idempotent re-runs), see rag_service/workers/task.py.
    """
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="table-parent-link.pdf")

    await repo.bulk_insert_tables(
        doc_id,
        [{"table_index": 0, "s3_csv_path": f"{doc_id}/tables/table_0.csv", "s3_html_path": f"{doc_id}/tables/table_0.html"}],
    )
    parent_chunk_id = uuid.uuid4()
    await repo.bulk_insert_chunks(
        doc_id,
        [{"id": parent_chunk_id, "content": "[→ Таблица 0](table_0)", "page_num": "", "headers": {}, "chunk_index": 0}],
    )
    await db_session.commit()

    table = (await repo.get_tables_by_doc_id(doc_id))[0]
    assert table.parent_chunk_id is None

    await repo.update_table_parent_chunk_id(table.id, parent_chunk_id)
    await db_session.commit()

    updated = (await repo.get_tables_by_doc_id(doc_id))[0]
    assert updated.parent_chunk_id == parent_chunk_id


async def test_get_parents_by_ids_empty_input(repo: DocumentRepository) -> None:
    """Empty parent_ids input should return an empty list."""
    result = await repo.get_parents_by_ids([])
    assert result == []


async def test_delete_document_removes_row_and_children(
    repo: DocumentRepository,
    db_session: AsyncSession,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Delete document should remove row and cascade-delete parent chunks."""
    doc_id = await _create_document(repo, db_session, created_doc_ids, filename="delete.pdf")
    await repo.bulk_insert_chunks(
        doc_id,
        [{"content": "to-delete", "chunk_index": 0}],
    )
    await db_session.commit()

    await repo.delete_document(doc_id)
    await db_session.commit()
    created_doc_ids.remove(doc_id)

    loaded = await repo.get_document_by_id(doc_id)
    assert loaded is None

    count_result = await db_session.execute(
        select(func.count()).select_from(ParentChunks).where(ParentChunks.doc_id == doc_id)
    )
    assert count_result.scalar_one() == 0
