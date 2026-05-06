from __future__ import annotations

"""Integration API test: upload-link -> presigned PUT -> webhook acceptance."""

import uuid
from unittest.mock import AsyncMock
from urllib.parse import urlparse
import sys
import types
import logging

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Test-local logger stub to avoid dependency on python-json-logger package.
if "rag_service.utils.logger_config" not in sys.modules:
    logger_stub = types.ModuleType("rag_service.utils.logger_config")

    def _setup_logger(name: str):
        return logging.getLogger(name)

    logger_stub.setup_logger = _setup_logger
    sys.modules["rag_service.utils.logger_config"] = logger_stub

from rag_service.api.rag_routes import router
from rag_service.application.document_orchestrator import DocumentOrchestrator
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.dependencies import (
    get_db_doc_service,
    get_document_orchestrator,
    get_task_dispatcher_service,
)
from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository
from rag_service.models import Base, DocumentListItemDTO
from rag_service.settings import settings


pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine():
    """Create engine and align schema for current integration flow."""
    assert settings.MODE == "TEST", "Integration tests must run with MODE=TEST"
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
    """Provide SQLAlchemy async session factory for DB assertions."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def s3_repository() -> S3StorageRepository:
    """Create real S3 repository and ensure bucket exists."""
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
async def api_client(session_factory, s3_repository: S3StorageRepository):
    """Build a test app with production router and dependency overrides."""
    app = FastAPI()
    app.include_router(router)

    db_service = DataBaseDocumentService(session_factory=session_factory)
    vector_mock = AsyncMock()
    orchestrator = DocumentOrchestrator(
        s3_storage=s3_repository,
        vector_storage=vector_mock,
        database=db_service,
    )
    dispatcher_mock = AsyncMock()

    async def _override_orchestrator():
        return orchestrator

    async def _override_db_service():
        return db_service

    async def _override_dispatcher():
        return dispatcher_mock

    app.dependency_overrides[get_document_orchestrator] = _override_orchestrator
    app.dependency_overrides[get_db_doc_service] = _override_db_service
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


def _extract_object_key_from_presigned_url(url: str) -> str:
    """Extract object key from MinIO path-style presigned URL."""
    parsed = urlparse(url)
    path = parsed.path.lstrip("/")
    _, object_key = path.split("/", 1)
    return object_key


async def test_upload_link_put_and_webhook_acceptance(
    api_client: AsyncClient,
    session_factory,
    created_doc_ids: list[uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create upload-link, upload bytes via URL, then submit webhook event."""
    filename = f"flow-{uuid.uuid4()}.pdf"
    content = b"integration-upload-webhook-content"

    print("\n[STEP 1] Request upload link")
    print("filename:", filename)
    print("file_size:", len(content))
    response = await api_client.post(
        "/documents/ingest/upload-link",
        params={"filename": filename, "file_size": len(content)},
    )
    print("upload-link status:", response.status_code)
    print("upload-link body:", response.text)
    assert response.status_code == 200
    body = response.json()
    doc_id = uuid.UUID(body["doc_id"])
    created_doc_ids.append(doc_id)
    presigned_url = body["presigned_url"]
    print("doc_id:", doc_id)
    print("presigned_url:", presigned_url)

    print("\n[STEP 2] Upload file to presigned URL (PUT)")
    async with httpx.AsyncClient() as external_client:
        put_response = await external_client.put(
            presigned_url,
            content=content,
            headers={"Content-Type": "application/pdf"},
        )
    print("put status:", put_response.status_code)
    print("put request headers:", dict(put_response.request.headers))
    print("put response headers:", dict(put_response.headers))
    print("put response text:", put_response.text)
    assert put_response.status_code in {200, 204}

    object_key = _extract_object_key_from_presigned_url(presigned_url)
    print("object_key extracted from url:", object_key)
    token = "test-webhook-token"
    monkeypatch.setenv("MINIO_WEBHOOK_TOKEN", token)

    print("\n[STEP 3] Send webhook event to API")
    webhook_payload = {"Records": [{"s3": {"object": {"key": object_key}}}]}
    print("webhook payload:", webhook_payload)
    webhook_response = await api_client.post(
        "/documents/ingest/webhook",
        json=webhook_payload,
        headers={"X-Minio-Extract-Token": token},
    )
    print("webhook status:", webhook_response.status_code)
    print("webhook body:", webhook_response.text)
    assert webhook_response.status_code == 200
    assert webhook_response.json().get("status") == "accepted"

    print("\n[STEP 4] Verify DB row exists")
    async with session_factory() as session:
        result = await session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id))
        document = result.scalar_one_or_none()
        print("db document exists:", document is not None)
        if document is not None:
            print("db document id:", document.id)
            print("db document filename:", document.filename)
            print("db document status:", document.status)
            print("db document s3key:", document.s3key)
        assert document is not None
        assert document.filename == filename
