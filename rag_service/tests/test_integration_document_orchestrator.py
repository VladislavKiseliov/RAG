from __future__ import annotations

"""Integration tests for ``DocumentOrchestrator`` against real infrastructure.

These tests are intentionally end-to-end at the service boundary and use:
- a real PostgreSQL test database for document persistence;
- a real MinIO bucket for object storage operations;
- a mocked vector storage dependency only where vector deletion is asserted.

Covered scenarios:
1. Registering a document and generating a presigned upload URL.
2. Reading file bytes from MinIO via orchestrator.
3. Listing documents enriched with object size from storage metadata.
4. Deleting a document across storage, vector layer call, and database row.
"""

import re
import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rag_service.application.document_orchestrator import DocumentOrchestrator
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository
from rag_service.models import Base, DocumentListItemDTO
from rag_service.settings import settings


pytestmark = pytest.mark.asyncio(loop_scope="module")

@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine():
    """Create and prepare the async SQLAlchemy engine for integration tests.

    Responsibilities:
    - enforce ``MODE=TEST`` safety guard;
    - ensure ``rag_kernel`` schema exists;
    - create tables from ORM metadata;
    - align selected columns/constraints used by current orchestrator flow.
    """
    assert settings.MODE == "TEST", "Integration tests must run with MODE=TEST"
    engine = create_async_engine(settings.DATABASE_URL, future=True)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS rag_kernel"))
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session_factory(engine):
    """Provide an async SQLAlchemy session factory bound to test engine."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def s3_repository() -> S3StorageRepository:
    """Build a real MinIO-backed repository and ensure ``test-bucket`` exists.

    The fixture creates the bucket lazily when absent so tests are repeatable
    across clean local environments.
    """
    repo = S3StorageRepository(
        endpoint_url="http://localhost:9000",
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket="test-bucket",
        secure=False,
    )
    async with repo._get_client() as client:
        buckets = await client.list_buckets()
        names = {b["Name"] for b in buckets.get("Buckets", [])}
        if repo.bucket not in names:
            await client.create_bucket(Bucket=repo.bucket)
    return repo


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def vector_storage_mock() -> AsyncMock:
    """Provide async mock for vector storage to verify delete-side effects."""
    mock = AsyncMock()
    mock.delete_vectors_by_id = AsyncMock()
    return mock


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def orchestrator(
    session_factory,
    s3_repository: S3StorageRepository,
    vector_storage_mock: AsyncMock,
) -> DocumentOrchestrator:
    """Construct ``DocumentOrchestrator`` with real DB/MinIO dependencies.

    Vector storage is mocked to keep tests deterministic and focused on:
    - orchestration behavior;
    - persistence consistency;
    - storage integration.
    """
    db_service = DataBaseDocumentService(session_factory=session_factory)
    return DocumentOrchestrator(
        s3_storage=s3_repository,
        vector_storage=vector_storage_mock,
        database=db_service,
    )


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def created_doc_ids():
    """Track created document IDs and remove them from DB in fixture teardown.

    This keeps integration tests idempotent and avoids long-term data buildup
    in the test database between runs.
    """
    ids: list[uuid.UUID] = []
    yield ids
    if not ids:
        return
    engine = create_async_engine(settings.DATABASE_URL, future=True)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        for doc_id in ids:
            await session.execute(
                text("DELETE FROM rag_kernel.documents WHERE id = :doc_id"),
                {"doc_id": doc_id},
            )
        await session.commit()
    await engine.dispose()

async def test_get_upload_link_persists_document_and_returns_presigned_url(
    orchestrator: DocumentOrchestrator,
    session_factory,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Ensure ``get_upload_link`` persists DB record and returns valid URL.

    Validates:
    - HTTP-like presigned URL shape;
    - generated object-key naming convention;
    - DB persistence of filename and minio key (column + metadata mirror).
    """
    filename = f"3-{uuid.uuid4()}.pdf"
    file_size = 512

    response = await orchestrator.get_upload_link(filename=filename, file_size=file_size)

    doc_id = uuid.UUID(response.doc_id)
    created_doc_ids.append(doc_id)

    assert response.presigned_url.startswith("http")
    assert "documents/" in response.presigned_url

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id))
        document = result.scalar_one_or_none()

    assert document is not None
    assert document.filename == filename
    assert document.s3key is not None
    assert re.match(
        r"^documents/\d{4}/\d{2}/[a-z0-9._-]+__[a-f0-9]{8}\.[a-z0-9]+$",
        document.s3key,
    )
    assert isinstance(document.meta, dict)
    assert document.meta.get("s3key") == document.s3key

async def test_get_file_reads_real_object_from_minio(
    orchestrator: DocumentOrchestrator,
    s3_repository: S3StorageRepository,
) -> None:
    """Ensure orchestrator reads exact bytes from a real MinIO object."""
    file_key = f"test_folder/{uuid.uuid4()}.txt"
    content = b"integration-minio-content"

    await s3_repository.upload_file(content=content, key=file_key, content_type="text/plain")
    loaded = await orchestrator.get_file(file_key)

    assert loaded == content

    await s3_repository.delete_file(file_key)


async def test_get_list_document_returns_size_and_status(
    orchestrator: DocumentOrchestrator,
    session_factory,
    s3_repository: S3StorageRepository,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """Ensure ``get_list_document`` returns DB fields and storage-derived size.

    Flow:
    - create document via orchestrator;
    - upload real bytes into MinIO under stored key;
    - verify list output contains status, key, and correct object size.
    """
    filename = f"list-{uuid.uuid4()}.pdf"
    content = b"list-document-content"

    response = await orchestrator.get_upload_link(filename=filename, file_size=len(content))
    doc_id = uuid.UUID(response.doc_id)
    created_doc_ids.append(doc_id)

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id))
        document = result.scalar_one()
    assert document.s3key is not None

    await s3_repository.upload_file(content=content, key=document.s3key, content_type="application/pdf")

    items = await orchestrator.get_list_document()
    row = next((x for x in items if x["doc_id"] == str(doc_id)), None)
    assert row is not None
    assert row["filename"] == filename
    assert row["status"] in {"pending", "processing"}
    assert row["size"] == len(content)
    assert row["s3key"] == document.s3key


async def test_delete_document_removes_file_vectors_and_db_record(
    orchestrator: DocumentOrchestrator,
    session_factory,
    s3_repository: S3StorageRepository,
    vector_storage_mock: AsyncMock,
) -> None:
    """Ensure ``delete_document`` performs full cleanup across all layers.

    Asserts:
    - object is removed from MinIO;
    - document row is removed from PostgreSQL;
    - vector deletion method is invoked with the target document id.
    """
    filename = f"delete-{uuid.uuid4()}.pdf"
    content = b"delete-document-content"

    response = await orchestrator.get_upload_link(filename=filename, file_size=len(content))
    doc_id = uuid.UUID(response.doc_id)

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id))
        document = result.scalar_one()
    assert document.s3key is not None

    await s3_repository.upload_file(content=content, key=document.s3key, content_type="application/pdf")
    await orchestrator.delete_document(str(doc_id))

    with pytest.raises(Exception):
        await s3_repository.stat(document.s3key)

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id))
        deleted = result.scalar_one_or_none()
    assert deleted is None
    vector_storage_mock.delete_vectors_by_id.assert_any_await(str(doc_id))


async def test_get_document_info_returns_full_postgres_payload(
    orchestrator: DocumentOrchestrator,
    created_doc_ids: list[uuid.UUID],
) -> None:
    filename = f"info-{uuid.uuid4()}.pdf"
    response = await orchestrator.get_upload_link(filename=filename, file_size=128)
    doc_id = uuid.UUID(response.doc_id)
    created_doc_ids.append(doc_id)

    info = await orchestrator.get_document_info(str(doc_id))

    assert info["doc_id"] == str(doc_id)
    assert info["filename"] == filename
    assert info["status"] in {"pending", "processing"}
    assert info["s3key"] is not None
    assert isinstance(info["meta"], dict)
    assert info["meta"].get("s3key") == info["s3key"]
    assert "created_at" in info
    assert "updated_at" in info
    assert "chunk_count" in info
    assert "chunks_total" in info


async def test_get_document_info_raises_for_missing_doc(
    orchestrator: DocumentOrchestrator,
) -> None:
    missing_doc_id = str(uuid.uuid4())
    with pytest.raises(ValueError, match="not found"):
        await orchestrator.get_document_info(missing_doc_id)
