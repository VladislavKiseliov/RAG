from __future__ import annotations

"""Integration tests for DocumentRepository against real PostgreSQL test DB."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rag_service.api.schemas import DocumentStatus
from rag_service.infrastructures.repositories.document_repository import DocumentRepository
from rag_service.models import Base, DocumentListItemDTO, ParentChunks
from rag_service.settings import settings


pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine():
    """Create engine and align schema to current model contract for repository tests."""
    assert settings.MODE == "TEST", "Repository integration tests must run with MODE=TEST"
    engine = create_async_engine(settings.DATABASE_URL, future=True)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS rag_kernel"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE rag_kernel.documents ALTER COLUMN file_hash DROP NOT NULL")
        )
        await conn.execute(text("ALTER TABLE rag_kernel.documents DROP CONSTRAINT IF EXISTS ck_documents_status"))
        await conn.execute(
            text(
                "ALTER TABLE rag_kernel.documents "
                "ALTER COLUMN status TYPE TEXT USING status::text"
            )
        )
        await conn.execute(text("DROP TYPE IF EXISTS rag_kernel.document_status_enum"))
        await conn.execute(
            text(
                "ALTER TABLE rag_kernel.documents "
                "ADD CONSTRAINT ck_documents_status "
                "CHECK (status IN ('pending', 'uploading', 'processing', 'extracting', 'indexing', 'completed', 'error'))"
            )
        )
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
    minio_key: str | None = None,
    metadata: dict | None = None,
) -> uuid.UUID:
    """Create and commit one document row for test setup."""
    doc_id = await repo.create_document(
        filename=filename,
        metadata=metadata or {"source": "repo-test"},
        minio_key=minio_key,
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
    """Create document and verify filename/status/meta/minio_key persistence."""
    key = f"documents/2026/04/{uuid.uuid4()}__a1b2c3d4.pdf"
    doc_id = await _create_document(
        repo,
        db_session,
        created_doc_ids,
        filename="manual.pdf",
        status=DocumentStatus.PENDING,
        minio_key=key,
        metadata={"origin": "integration"},
    )

    loaded = await repo.get_document_by_id(doc_id)
    assert loaded is not None
    assert loaded.filename == "manual.pdf"
    assert loaded.status == "pending"
    assert loaded.minio_key == key
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
        minio_key="documents/2026/04/update__11112222.pdf",
        file_hash="b" * 64,
    )
    await db_session.commit()

    loaded = await repo.get_document_by_id(doc_id)
    assert loaded is not None
    assert loaded.status == "uploading"
    assert loaded.meta == {"source": "repo-update"}
    assert loaded.chunk_count == 5
    assert loaded.minio_key == "documents/2026/04/update__11112222.pdf"
    assert loaded.file_hash == "b" * 64


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
