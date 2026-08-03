from __future__ import annotations

"""Integration API test: upload-link -> presigned PUT -> webhook dispatch.

Exercises the real FastAPI router (`rag_routes.router`) + exception handlers
against a real Postgres test DB and a real MinIO test bucket. Celery dispatch
itself is mocked out via `get_task_dispatcher_service` override - the target
here is the HTTP/DB/storage wiring, not the Celery broker.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from rag_service.api.exception_handlers import register_exception_handlers
from rag_service.api.rag_routes import router
from rag_service.application.document_orchestrator import DocumentOrchestrator
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.dependencies import get_document_orchestrator, get_task_dispatcher_service
from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository
from rag_service.models import Base, DocumentListItemDTO
from rag_service.settings import settings


pytestmark = pytest.mark.asyncio(loop_scope="module")

TEST_BUCKET = "test-bucket"


class _TestBucketStorage:
    """Bucket-scoped adapter bound to the disposable test bucket - see the same
    helper in test_integration_document_orchestrator.py (no shared conftest yet)."""

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
    """Provide SQLAlchemy async session factory for DB assertions."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def s3_repository() -> S3StorageRepository:
    """Create real S3 repository and ensure the disposable test bucket exists."""
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
async def dispatcher_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.dispatch_ingestion = AsyncMock()
    return mock


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def api_client(session_factory, s3_repository: S3StorageRepository, dispatcher_mock: AsyncMock):
    """Build a test app with the production router + exception handlers and dependency overrides."""
    app = FastAPI()
    app.include_router(router)
    register_exception_handlers(app)

    db_service = DataBaseDocumentService(session_factory=session_factory)
    vector_mock = AsyncMock()
    orchestrator = DocumentOrchestrator(
        s3_storage=_TestBucketStorage(s3_repository),
        vector_storage=vector_mock,
        database=db_service,
    )

    async def _override_orchestrator():
        return orchestrator

    async def _override_dispatcher():
        return dispatcher_mock

    app.dependency_overrides[get_document_orchestrator] = _override_orchestrator
    app.dependency_overrides[get_task_dispatcher_service] = _override_dispatcher

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def created_doc_ids(session_factory):
    """Track created document IDs and remove them after each test."""
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


async def test_upload_link_put_and_webhook_dispatches_ingestion(
    api_client: AsyncClient,
    session_factory,
    created_doc_ids: list[uuid.UUID],
    dispatcher_mock: AsyncMock,
) -> None:
    """Create upload-link, upload bytes via presigned PUT, then submit webhook event."""
    filename = f"flow-{uuid.uuid4()}.pdf"
    content = b"integration-upload-webhook-content"

    response = await api_client.post(
        "/documents/ingest/upload-link",
        params={"filename": filename, "file_size": len(content)},
    )
    assert response.status_code == 200
    body = response.json()
    doc_id = uuid.UUID(body["doc_id"])
    created_doc_ids.append(doc_id)
    presigned_url = body["presigned_url"]

    async with httpx.AsyncClient() as external_client:
        put_response = await external_client.put(
            presigned_url,
            content=content,
            headers={"Content-Type": "application/pdf"},
        )
    assert put_response.status_code in {200, 204}

    s3key = f"{doc_id}/{filename}"
    webhook_payload = {"Records": [{"s3": {"object": {"key": s3key}}}]}
    webhook_response = await api_client.post(
        "/documents/ingest/webhook",
        json=webhook_payload,
        headers={"Authorization": f"Bearer {settings.minio_notify_webhook_auth_token_1}"},
    )
    assert webhook_response.status_code == 200
    assert webhook_response.json().get("status") == "accepted"
    dispatcher_mock.dispatch_ingestion.assert_awaited_once_with(s3key=s3key)

    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id))
        document = result.scalar_one_or_none()
        assert document is not None
        assert document.filename == filename
        assert document.s3key == s3key


async def test_webhook_rejects_missing_or_wrong_token(
    api_client: AsyncClient,
    dispatcher_mock: AsyncMock,
) -> None:
    dispatcher_mock.reset_mock()
    webhook_payload = {"Records": [{"s3": {"object": {"key": "irrelevant.pdf"}}}]}

    no_auth = await api_client.post("/documents/ingest/webhook", json=webhook_payload)
    assert no_auth.status_code == 401

    wrong_token = await api_client.post(
        "/documents/ingest/webhook",
        json=webhook_payload,
        headers={"Authorization": "Bearer definitely-wrong-token"},
    )
    assert wrong_token.status_code == 401
    dispatcher_mock.dispatch_ingestion.assert_not_called()


async def test_upload_link_rejects_duplicate_filename(
    api_client: AsyncClient,
    created_doc_ids: list[uuid.UUID],
) -> None:
    filename = f"dup-{uuid.uuid4()}.pdf"

    first = await api_client.post(
        "/documents/ingest/upload-link",
        params={"filename": filename, "file_size": 128},
    )
    assert first.status_code == 200
    created_doc_ids.append(uuid.UUID(first.json()["doc_id"]))

    second = await api_client.post(
        "/documents/ingest/upload-link",
        params={"filename": filename, "file_size": 128},
    )
    assert second.status_code == 409
