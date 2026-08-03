from __future__ import annotations

"""Integration tests for DataBaseDocumentService on a real test PostgreSQL DB.

The suite seeds multiple documents with different statuses and verifies that
service methods work against real models state (not mocks).
"""

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rag_service.application.document_service import DataBaseDocumentService
from rag_service.models import Base, DocumentChapters, DocumentListItemDTO, DocumentStatus, DocumentTables, ParentChunks
from rag_service.settings import settings


pytestmark = pytest.mark.asyncio(loop_scope="module")

SEEDED_DOCUMENTS = [
    {
        "id": uuid.uuid4(),
        "filename": "seed-pending.pdf",
        "status": "pending",
        "file_hash": None,
        "s3key": "documents/2026/04/seed-pending__aaaa1111.pdf",
        "meta": {"source": "seed", "tag": "pending"},
        "chunk_count": 0,
    },
    {
        "id": uuid.uuid4(),
        "filename": "seed-processing.pdf",
        "status": "processing",
        "file_hash": "f" * 64,
        "s3key": "documents/2026/04/seed-processing__bbbb2222.pdf",
        "meta": {"source": "seed", "tag": "processing"},
        "chunk_count": None,
    },
    {
        "id": uuid.uuid4(),
        "filename": "seed-completed.pdf",
        "status": "completed",
        "file_hash": "e" * 64,
        "s3key": "documents/2026/04/seed-completed__cccc3333.pdf",
        "meta": {"source": "seed", "tag": "completed"},
        "chunk_count": 3,
    },
]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine():
    """Create engine against a disposable test schema, rebuilt fresh from current ORM metadata.

    The test DB accumulates schema drift across app versions (`Base.metadata.create_all`
    only adds missing tables, never missing columns on tables that already exist) - see
    D11 in rag_service/ISSUES.md. Dropping and recreating `rag_kernel` guarantees the
    schema always matches the current models, instead of patching individual columns.
    """
    assert settings.MODE == "TEST", "Integration tests must run with MODE=TEST"
    engine = create_async_engine(settings.DATABASE_URL, future=True)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS rag_kernel CASCADE"))
        await conn.execute(text("CREATE SCHEMA rag_kernel"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session_factory(engine):
    """Provide async session factory bound to real test PostgreSQL engine."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def service(session_factory) -> DataBaseDocumentService:
    """Instantiate DataBaseDocumentService used by integration tests."""
    return DataBaseDocumentService(session_factory=session_factory)


@pytest_asyncio.fixture(scope="module", loop_scope="module", autouse=True)
async def seeded_data(session_factory):
    """Seed test DB with documents in multiple statuses and parent chunks."""
    async with session_factory() as session:
        for item in SEEDED_DOCUMENTS:
            session.add(
                DocumentListItemDTO(
                    id=item["id"],
                    filename=item["filename"],
                    file_hash=item["file_hash"],
                    status=item["status"],
                    s3key=item["s3key"],
                    meta=item["meta"],
                    chunk_count=item["chunk_count"],
                )
            )
        await session.commit()

    # Add parent chunks only for processing seed (chunk_count is None there).
    processing_doc_id = SEEDED_DOCUMENTS[1]["id"]
    async with session_factory() as session:
        session.add_all(
            [
                ParentChunks(
                    id=uuid.uuid4(),
                    doc_id=processing_doc_id,
                    content="seed chunk 1",
                    chunk_index=0,
                    page_num="1",
                    headers={"h1": "A"},
                ),
                ParentChunks(
                    id=uuid.uuid4(),
                    doc_id=processing_doc_id,
                    content="seed chunk 2",
                    chunk_index=1,
                    page_num="1",
                    headers={"h1": "A"},
                ),
            ]
        )
        await session.commit()

    yield

    # Cleanup seeded rows.
    async with session_factory() as session:
        for item in SEEDED_DOCUMENTS:
            await session.execute(
                text("DELETE FROM rag_kernel.documents WHERE id = :doc_id"),
                {"doc_id": item["id"]},
            )
        await session.commit()


async def test_get_document_by_id_reads_seeded_document(service: DataBaseDocumentService) -> None:
    """Read one seeded document by id and verify core fields."""
    target = SEEDED_DOCUMENTS[0]
    doc = await service.get_document_by_id(target["id"])
    assert doc is not None
    assert doc.id == target["id"]
    assert doc.filename == target["filename"]
    assert doc.status == target["status"]


async def test_list_documents_filters_by_status(service: DataBaseDocumentService) -> None:
    """List documents with status filter and ensure only matching records are returned."""
    items = await service.list_documents(limit=100, offset=0, status="completed")
    assert len(items) >= 1
    assert all(item.status == "completed" for item in items)


async def test_get_document_full_info_returns_chunk_count(service: DataBaseDocumentService) -> None:
    """Return full info payload with Postgres-stored fields."""
    target = SEEDED_DOCUMENTS[1]  # processing doc with chunk_count=None
    info = await service.get_document_full_info(target["id"])
    assert info is not None
    assert info["doc_id"] == str(target["id"])
    assert info["filename"] == target["filename"]
    assert info["status"] == "processing"
    assert info["s3key"] == target["s3key"]
    assert info["meta"]["tag"] == "processing"
    assert info["chunk_count"] is None
    assert isinstance(info["created_at"], datetime)


async def test_create_doc_persists_s3key_and_meta(
    service: DataBaseDocumentService,
    session_factory,
) -> None:
    """Create a new document and verify minio key + metadata models."""
    new_doc_id = uuid.uuid4()
    filename = "created-from-service.pdf"
    s3key = "documents/2026/04/created-from-service__dddd4444.pdf"
    await service.create_doc(
        doc_id=new_doc_id,
        filename=filename,
        metadata={"source": "test-create"},
        s3key=s3key,
    )

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == new_doc_id))
        created = result.scalar_one_or_none()
        assert created is not None
        assert created.filename == filename
        assert created.s3key == s3key
        assert created.meta == {"source": "test-create"}
        assert created.status == DocumentStatus.PENDING

        await session.execute(text("DELETE FROM rag_kernel.documents WHERE id = :doc_id"), {"doc_id": new_doc_id})
        await session.commit()


async def test_set_status_updates_status_and_chunk_count(
    service: DataBaseDocumentService,
    session_factory,
) -> None:
    """Update status/chunk_count and verify persisted values."""
    target = SEEDED_DOCUMENTS[0]["id"]
    await service.set_status(target, DocumentStatus.COMPLETED, chunk_count=7)

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == target))
        doc = result.scalar_one()
        assert doc.status == "completed"
        assert doc.chunk_count == 7


async def test_update_document_updates_selected_fields(
    service: DataBaseDocumentService,
    session_factory,
) -> None:
    """Update multiple fields via the update_data dict and verify persisted values."""
    target = SEEDED_DOCUMENTS[0]["id"]
    new_meta = {"source": "updated", "tag": "after-update"}
    new_key = "documents/2026/04/updated__ffff6666.pdf"
    new_hash = "a" * 64

    await service.update_document(
        target,
        update_data={
            "status": DocumentStatus.UPLOAD,
            "metadata": new_meta,
            "chunk_count": 9,
            "s3key": new_key,
            "file_hash": new_hash,
        },
    )

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == target))
        doc = result.scalar_one()
        assert doc.status == "uploading"
        assert doc.meta == new_meta
        assert doc.chunk_count == 9
        assert doc.s3key == new_key
        assert doc.file_hash == new_hash


async def test_add_document_chapters_persists_rows(
    service: DataBaseDocumentService,
    session_factory,
) -> None:
    """add_document_chapters should insert rows scoped to the target document."""
    target = SEEDED_DOCUMENTS[0]["id"]

    await service.add_document_chapters(
        target,
        [{"chapter_number": "1", "title": "Введение", "s3_md_path": f"{target}/chapters/chapter_1.md"}],
    )

    async with session_factory() as session:
        result = await session.execute(select(DocumentChapters).where(DocumentChapters.doc_id == target))
        rows = list(result.scalars().all())
        assert len(rows) == 1
        assert rows[0].chapter_number == "1"
        assert rows[0].title == "Введение"

        await session.execute(text("DELETE FROM rag_kernel.document_chapters WHERE doc_id = :doc_id"), {"doc_id": target})
        await session.commit()


async def test_add_document_chapters_empty_list_is_noop(
    service: DataBaseDocumentService,
    session_factory,
) -> None:
    """Empty chapters list should not touch the database or open a session."""
    target = SEEDED_DOCUMENTS[0]["id"]

    await service.add_document_chapters(target, [])

    async with session_factory() as session:
        result = await session.execute(select(DocumentChapters).where(DocumentChapters.doc_id == target))
        assert list(result.scalars().all()) == []


async def test_add_document_tables_persists_rows(
    service: DataBaseDocumentService,
    session_factory,
) -> None:
    """add_document_tables should insert rows scoped to the target document."""
    target = SEEDED_DOCUMENTS[0]["id"]

    await service.add_document_tables(
        target,
        [{
            "table_index": 0,
            "s3_csv_path": f"{target}/tables/table_0.csv",
            "s3_html_path": f"{target}/tables/table_0.html",
        }],
    )

    async with session_factory() as session:
        result = await session.execute(select(DocumentTables).where(DocumentTables.doc_id == target))
        rows = list(result.scalars().all())
        assert len(rows) == 1
        assert rows[0].table_index == 0

        await session.execute(text("DELETE FROM rag_kernel.document_tables WHERE doc_id = :doc_id"), {"doc_id": target})
        await session.commit()


async def test_delete_document_removes_row(service: DataBaseDocumentService, session_factory) -> None:
    """Delete a document and ensure it no longer exists in database."""
    temp_id = uuid.uuid4()
    await service.create_doc(
        doc_id=temp_id,
        filename="to-delete.pdf",
        metadata={"tmp": True},
        s3key="documents/2026/04/to-delete__eeee5555.pdf",
    )
    await service.delete_document(temp_id)

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == temp_id))
        assert result.scalar_one_or_none() is None
