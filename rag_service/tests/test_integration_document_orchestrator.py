from __future__ import annotations

"""Integration tests for ``DocumentOrchestrator`` against real infrastructure.

These tests are intentionally end-to-end at the service boundary and use:
- a real PostgreSQL test database for document models;
- a real MinIO test bucket for object storage operations;
- a mocked vector storage dependency only where vector deletion is asserted.

Covered scenarios:
1. Registering a document and generating a presigned upload URL.
2. Reading file bytes from MinIO via orchestrator.
3. Listing documents enriched with the Postgres-stored file size.
4. Deleting a document across storage, vector layer call, and database row.
5. Generating a presigned inline-view URL for the original file.
"""

import re
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rag_service.application.document_orchestrator import DocumentOrchestrator
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.domain.errors.postgres import DocumentNotFound
from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository
from rag_service.models import Base, DocumentListItemDTO
from rag_service.settings import settings


pytestmark = pytest.mark.asyncio(loop_scope="module")

TEST_BUCKET = "test-bucket"


class _TestBucketStorage:
    """Bucket-scoped BucketStorageProvider adapter bound to the disposable test
    bucket, mirroring KnowledgeBaseStorageService without touching the real
    `knowledge-base` production bucket (see rag_service/ISSUES.md D11)."""

    def __init__(self, store: S3StorageRepository) -> None:
        self._store = store
        self._bucket = TEST_BUCKET

    async def upload_file(self, content: bytes, key: str, content_type: str) -> None:
        await self._store.upload_file(content, key, content_type, bucket=self._bucket)

    async def get_file(self, key: str) -> bytes:
        return await self._store.get_file(key, bucket=self._bucket)

    async def delete_file(self, key: str) -> None:
        await self._store.delete_file(key, bucket=self._bucket)

    async def generate_presigned_url(self, key: str, expiration: int = 300) -> str:
        return await self._store.generate_presigned_url(key, bucket=self._bucket, expiration=expiration)

    async def generate_presigned_download_url(
        self, key: str, *, expiration: int = 300, filename: str | None = None
    ) -> str:
        return await self._store.generate_presigned_download_url(
            key, bucket=self._bucket, expiration=expiration, filename=filename
        )

    async def stat(self, key: str) -> dict[str, Any]:
        return await self._store.stat(key, bucket=self._bucket)

    async def list(self, prefix: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        return await self._store.list(bucket=self._bucket, prefix=prefix, limit=limit)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine():
    """Create engine against a disposable test schema, rebuilt fresh from current ORM metadata."""
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
    """Provide an async SQLAlchemy session factory bound to test engine."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def s3_repository() -> S3StorageRepository:
    """Build a real MinIO-backed repository and ensure the disposable test bucket exists."""
    repo = S3StorageRepository(
        private_endpoint_url=settings.minio_private_url,
        public_endpoint_url=settings.minio_public_url,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
    )
    async with repo._get_client() as client:
        buckets = await client.list_buckets()
        names = {b["Name"] for b in buckets.get("Buckets", [])}
        if TEST_BUCKET not in names:
            await client.create_bucket(Bucket=TEST_BUCKET)
    return repo


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def vector_storage_mock() -> AsyncMock:
    """Provide async mock for vector storage to verify delete-side effects."""
    mock = AsyncMock()
    mock.delete_by_field = AsyncMock()
    return mock


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def orchestrator(
    session_factory,
    s3_repository: S3StorageRepository,
    vector_storage_mock: AsyncMock,
) -> DocumentOrchestrator:
    """Construct ``DocumentOrchestrator`` with real DB/MinIO dependencies.

    Vector storage is mocked to keep tests deterministic and focused on
    orchestration behavior, models consistency, and storage integration.
    """
    db_service = DataBaseDocumentService(session_factory=session_factory)
    return DocumentOrchestrator(
        s3_storage=_TestBucketStorage(s3_repository),
        vector_storage=vector_storage_mock,
        database=db_service,
    )


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def created_doc_ids():
    """Track created document IDs and remove them from DB in fixture teardown."""
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
    """Ensure ``get_upload_link`` persists DB record and returns a valid presigned URL.

    The S3 key convention is `{doc_uuid}/{sanitized_filename}` (see
    IngestionDocument.create_new / T18 in ISSUES.md) - not the older
    date-bucketed `documents/YYYY/MM/...` layout.
    """
    filename = f"3-{uuid.uuid4()}.pdf"
    file_size = 512

    response = await orchestrator.get_upload_link(filename=filename, file_size=file_size)

    doc_id = uuid.UUID(response.doc_id)
    created_doc_ids.append(doc_id)

    assert response.presigned_url.startswith("http")
    assert f"{doc_id}/{filename}" in response.presigned_url

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id))
        document = result.scalar_one_or_none()

    assert document is not None
    assert document.filename == filename
    assert document.s3key == f"{doc_id}/{filename}"
    assert re.match(r"^[0-9a-f-]+/[a-z0-9._-]+\.pdf$", document.s3key)


async def test_get_file_reads_real_object_from_minio(
    orchestrator: DocumentOrchestrator,
    s3_repository: S3StorageRepository,
) -> None:
    """Ensure orchestrator reads exact bytes from a real MinIO object."""
    file_key = f"test_folder/{uuid.uuid4()}.txt"
    content = b"integration-minio-content"

    await s3_repository.upload_file(content=content, key=file_key, content_type="text/plain", bucket=TEST_BUCKET)
    loaded = await orchestrator.get_file_s3_by_s3key(file_key)

    assert loaded == content

    await s3_repository.delete_file(file_key, TEST_BUCKET)


async def test_get_list_document_returns_postgres_stored_size_and_status(
    orchestrator: DocumentOrchestrator,
    created_doc_ids: list[uuid.UUID],
) -> None:
    """get_list_document reports `file_size` as stored in Postgres at creation time
    (not a live S3 stat() - see DocumentOrchestrator.get_list_document)."""
    filename = f"list-{uuid.uuid4()}.pdf"
    file_size = 2048

    response = await orchestrator.get_upload_link(filename=filename, file_size=file_size)
    doc_id = uuid.UUID(response.doc_id)
    created_doc_ids.append(doc_id)

    items = await orchestrator.get_list_document()
    row = next((x for x in items if x["doc_id"] == str(doc_id)), None)
    assert row is not None
    assert row["filename"] == filename
    assert row["status"] == "pending"
    assert row["size"] == file_size
    assert row["s3key"] == f"{doc_id}/{filename}"


async def test_delete_document_removes_file_vectors_and_db_record(
    orchestrator: DocumentOrchestrator,
    session_factory,
    s3_repository: S3StorageRepository,
    vector_storage_mock: AsyncMock,
) -> None:
    """Ensure ``delete_document`` performs full cleanup across all layers."""
    filename = f"delete-{uuid.uuid4()}.pdf"
    content = b"delete-document-content"

    response = await orchestrator.get_upload_link(filename=filename, file_size=len(content))
    doc_id = uuid.UUID(response.doc_id)

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id))
        document = result.scalar_one()
    assert document.s3key is not None

    await s3_repository.upload_file(content=content, key=document.s3key, content_type="application/pdf", bucket=TEST_BUCKET)
    await orchestrator.delete_document(doc_id)

    with pytest.raises(Exception):
        await s3_repository.stat(document.s3key, TEST_BUCKET)

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id))
        deleted = result.scalar_one_or_none()
    assert deleted is None
    vector_storage_mock.delete_by_field.assert_any_await("doc_id", str(doc_id))


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
    assert info["status"] == "pending"
    assert info["s3key"] is not None
    assert isinstance(info["meta"], dict)
    assert "created_at" in info
    assert "updated_at" in info
    assert "chunk_count" in info


async def test_get_document_info_raises_for_missing_doc(
    orchestrator: DocumentOrchestrator,
) -> None:
    missing_doc_id = str(uuid.uuid4())
    with pytest.raises(DocumentNotFound):
        await orchestrator.get_document_info(missing_doc_id)


async def test_get_file_url_returns_presigned_inline_url(
    orchestrator: DocumentOrchestrator,
    s3_repository: S3StorageRepository,
    created_doc_ids: list[uuid.UUID],
) -> None:
    filename = f"view-{uuid.uuid4()}.pdf"
    content = b"inline-view-content"
    response = await orchestrator.get_upload_link(filename=filename, file_size=len(content))
    doc_id = uuid.UUID(response.doc_id)
    created_doc_ids.append(doc_id)

    await s3_repository.upload_file(content=content, key=f"{doc_id}/{filename}", content_type="application/pdf", bucket=TEST_BUCKET)

    url = await orchestrator.get_file_url(doc_id)

    assert url is not None
    assert "response-content-disposition=inline" in url

    await s3_repository.delete_file(f"{doc_id}/{filename}", TEST_BUCKET)


async def test_get_file_url_returns_none_for_missing_doc(
    orchestrator: DocumentOrchestrator,
) -> None:
    assert await orchestrator.get_file_url(uuid.uuid4()) is None
