from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from rag_service.infrastructures.repositories.s3_storage_repository import DocumentStorageRepository


@pytest.fixture
def provider() -> AsyncMock:
    mock = AsyncMock()
    mock.upload = AsyncMock()
    mock.download = AsyncMock()
    mock.stat = AsyncMock()
    mock.list = AsyncMock()
    mock.delete = AsyncMock()
    return mock


@pytest.fixture
def repository(provider: AsyncMock) -> DocumentStorageRepository:
    return DocumentStorageRepository(provider)


@pytest.mark.asyncio
async def test_upload_file_calls_provider(repository: DocumentStorageRepository, provider: AsyncMock) -> None:
    await repository.upload_file(b"data", "documents/1/file.pdf", "application/pdf")

    provider.upload.assert_awaited_once_with(b"data", "documents/1/file.pdf", content_type="application/pdf")


@pytest.mark.asyncio
async def test_get_file_returns_provider_data(repository: DocumentStorageRepository, provider: AsyncMock) -> None:
    provider.download.return_value = b"file-bytes"

    result = await repository.get_file_s3_by_s3key("documents/1/file.pdf")

    assert result == b"file-bytes"
    provider.download.assert_awaited_once_with("documents/1/file.pdf")


@pytest.mark.asyncio
async def test_get_file_metadata_returns_provider_stat(
    repository: DocumentStorageRepository,
    provider: AsyncMock,
) -> None:
    provider.stat.return_value = {"key": "documents/1/file.pdf", "size": 123}

    result = await repository.get_file_metadata("documents/1/file.pdf")

    assert result == {"key": "documents/1/file.pdf", "size": 123}
    provider.stat.assert_awaited_once_with("documents/1/file.pdf")


@pytest.mark.asyncio
async def test_list_files_returns_provider_list(repository: DocumentStorageRepository, provider: AsyncMock) -> None:
    provider.list.return_value = [{"key": "documents/1/file.pdf"}]

    result = await repository.list_files(prefix="documents/1", limit=10)

    assert result == [{"key": "documents/1/file.pdf"}]
    provider.list.assert_awaited_once_with(prefix="documents/1", limit=10)


@pytest.mark.asyncio
async def test_delete_file_calls_provider(repository: DocumentStorageRepository, provider: AsyncMock) -> None:
    await repository.delete_file("documents/1/file.pdf")

    provider.delete.assert_awaited_once_with("documents/1/file.pdf")
