import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from backend.services.document_upload_service import DocumentUploadService, MAX_FILE_SIZE
from rag_service.models import DocumentStatus


@pytest.fixture
def document_service_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.get_document_by_hash = AsyncMock()
    mock.create_doc = AsyncMock()
    return mock


@pytest.fixture
def storage_repository_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.upload_file = AsyncMock()
    return mock


@pytest.fixture
def enqueue_ingestion_mock() -> Mock:
    return Mock()


@pytest.fixture
def upload_service(
    document_service_mock: AsyncMock,
    storage_repository_mock: AsyncMock,
    enqueue_ingestion_mock: Mock,
) -> DocumentUploadService:
    return DocumentUploadService(
        document_service=document_service_mock,
        storage_repository=storage_repository_mock,
        enqueue_ingestion=enqueue_ingestion_mock,
    )


@pytest.mark.asyncio
async def test_upload_document_raises_for_unsupported_extension(upload_service: DocumentUploadService) -> None:
    with pytest.raises(ValueError, match="Unsupported file extension"):
        await upload_service.upload_document(filename="manual.exe", content=b"abc", content_type="application/pdf")


@pytest.mark.asyncio
async def test_upload_document_raises_for_unsupported_content_type(upload_service: DocumentUploadService) -> None:
    with pytest.raises(ValueError, match="Unsupported content type"):
        await upload_service.upload_document(filename="manual.pdf", content=b"abc", content_type="image/png")


@pytest.mark.asyncio
async def test_upload_document_raises_for_empty_content(upload_service: DocumentUploadService) -> None:
    with pytest.raises(ValueError, match="Empty file"):
        await upload_service.upload_document(filename="manual.pdf", content=b"", content_type="application/pdf")


@pytest.mark.asyncio
async def test_upload_document_raises_for_large_file(upload_service: DocumentUploadService) -> None:
    with pytest.raises(OverflowError, match="File too large"):
        await upload_service.upload_document(
            filename="manual.pdf",
            content=b"a" * (MAX_FILE_SIZE + 1),
            content_type="application/pdf",
        )


@pytest.mark.asyncio
async def test_upload_document_returns_duplicate_response(
    upload_service: DocumentUploadService,
    document_service_mock: AsyncMock,
    storage_repository_mock: AsyncMock,
) -> None:
    existing_id = uuid.uuid4()
    existing = SimpleNamespace(
        id=existing_id,
        filename="existing.pdf",
        status=DocumentStatus.completed,
    )
    document_service_mock.get_document_by_hash.return_value = existing

    response = await upload_service.upload_document(
        filename="manual.pdf",
        content=b"abc",
        content_type="application/pdf",
    )

    assert response.uploaded == 0
    assert response.skipped == 1
    assert response.files == []
    assert len(response.duplicates) == 1
    assert response.duplicates[0].doc_id == str(existing_id)
    storage_repository_mock.upload_file.assert_not_called()
    document_service_mock.create_doc.assert_not_called()


@pytest.mark.asyncio
async def test_upload_document_creates_doc_uploads_to_minio_and_enqueues_task(
    upload_service: DocumentUploadService,
    document_service_mock: AsyncMock,
    storage_repository_mock: AsyncMock,
    enqueue_ingestion_mock: Mock,
) -> None:
    content = b"pdf-content"
    file_hash = hashlib.sha256(content).hexdigest()
    created_id = uuid.uuid4()
    document_service_mock.get_document_by_hash.return_value = None
    document_service_mock.create_doc.return_value = created_id

    with patch("backend.services.document_upload_service.uuid.uuid4", return_value=created_id):
        response = await upload_service.upload_document(
            filename="manual.pdf",
            content=content,
            content_type="application/pdf",
        )

    storage_repository_mock.upload_file.assert_awaited_once_with(
        content,
        f"documents/{created_id}/manual.pdf",
        content_type="application/pdf",
    )
    document_service_mock.create_doc.assert_awaited_once_with(
        filename="manual.pdf",
        file_hash=file_hash,
        meta={"minio_key": f"documents/{created_id}/manual.pdf", "content_type": "application/pdf"},
        doc_id=created_id,
    )
    enqueue_ingestion_mock.assert_called_once_with(
        doc_id=str(created_id),
        minio_key=f"documents/{created_id}/manual.pdf",
        filename="manual.pdf",
    )
    assert response.uploaded == 1
    assert response.skipped == 0
    assert len(response.files) == 1
    assert response.files[0].doc_id == str(created_id)
    assert response.files[0].status == DocumentStatus.processing.value
    assert response.duplicates == []


@pytest.mark.asyncio
async def test_upload_document_allows_replacing_error_document(
    upload_service: DocumentUploadService,
    document_service_mock: AsyncMock,
) -> None:
    errored = SimpleNamespace(
        id=uuid.uuid4(),
        filename="broken.pdf",
        status=DocumentStatus.error,
    )
    created_id = uuid.uuid4()
    document_service_mock.get_document_by_hash.return_value = errored
    document_service_mock.create_doc.return_value = created_id

    with patch("backend.services.document_upload_service.uuid.uuid4", return_value=created_id):
        response = await upload_service.upload_document(
            filename="manual.pdf",
            content=b"abc",
            content_type="application/pdf",
        )

    assert response.uploaded == 1
    document_service_mock.create_doc.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_document_uses_default_content_type_when_missing(
    upload_service: DocumentUploadService,
    document_service_mock: AsyncMock,
    storage_repository_mock: AsyncMock,
) -> None:
    created_id = uuid.uuid4()
    document_service_mock.get_document_by_hash.return_value = None
    document_service_mock.create_doc.return_value = created_id

    with patch("backend.services.document_upload_service.uuid.uuid4", return_value=created_id):
        await upload_service.upload_document(
            filename="manual.pdf",
            content=b"abc",
            content_type=None,
        )

    storage_repository_mock.upload_file.assert_awaited_once_with(
        b"abc",
        f"documents/{created_id}/manual.pdf",
        content_type="application/octet-stream",
    )


@pytest.mark.asyncio
async def test_get_file_delegates_to_storage_repository(
    upload_service: DocumentUploadService,
    storage_repository_mock: AsyncMock,
) -> None:
    storage_repository_mock.get_file.return_value = b"file-content"

    result = await upload_service.get_file(key="documents/1/manual.pdf")

    assert result == b"file-content"
    storage_repository_mock.get_file.assert_awaited_once_with("documents/1/manual.pdf")


@pytest.mark.asyncio
async def test_get_file_metadata_delegates_to_storage_repository(
    upload_service: DocumentUploadService,
    storage_repository_mock: AsyncMock,
) -> None:
    storage_repository_mock.get_file_metadata.return_value = {"key": "documents/1/manual.pdf", "size": 123}

    result = await upload_service.get_file_metadata(key="documents/1/manual.pdf")

    assert result == {"key": "documents/1/manual.pdf", "size": 123}
    storage_repository_mock.get_file_metadata.assert_awaited_once_with("documents/1/manual.pdf")


@pytest.mark.asyncio
async def test_list_files_delegates_to_storage_repository(
    upload_service: DocumentUploadService,
    storage_repository_mock: AsyncMock,
) -> None:
    storage_repository_mock.list_files.return_value = [{"key": "documents/1/manual.pdf"}]

    result = await upload_service.list_files(prefix="documents/1", limit=10)

    assert result == [{"key": "documents/1/manual.pdf"}]
    storage_repository_mock.list_files.assert_awaited_once_with(prefix="documents/1", limit=10)


@pytest.mark.asyncio
async def test_delete_file_delegates_to_storage_repository(
    upload_service: DocumentUploadService,
    storage_repository_mock: AsyncMock,
) -> None:
    result = await upload_service.delete_file(key="documents/1/manual.pdf")

    assert result == {"status": "deleted", "key": "documents/1/manual.pdf"}
    storage_repository_mock.delete_file.assert_awaited_once_with("documents/1/manual.pdf")
