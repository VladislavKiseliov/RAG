import uuid

import aiohttp
import pytest
from yarl import URL

from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository
from rag_service.settings import settings


@pytest.fixture
async def s3_repository() -> S3StorageRepository:
    return S3StorageRepository(
        endpoint_url="http://localhost:9000",
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket="test-bucket",
        secure=False,
    )


@pytest.mark.asyncio
async def test_s3_upload_get_presigned_and_delete(s3_repository: S3StorageRepository) -> None:
    file_content = b"Hello, RAG world!"
    file_key = f"test_folder/{uuid.uuid4()}.txt"

    await s3_repository.upload_file(
        content=file_content,
        key=file_key,
        content_type="text/plain",
    )

    downloaded_content = await s3_repository.get_file(file_key)
    assert downloaded_content == file_content

    await s3_repository.delete_file(file_key)
    with pytest.raises(Exception):
        await s3_repository.get_file(file_key)


@pytest.mark.asyncio
async def test_s3_presigned_put_then_read_and_delete(s3_repository: S3StorageRepository) -> None:
    file_content = b"Hello from presigned PUT!"
    file_key = f"test_folder/{uuid.uuid4()}.txt"

    presigned_url = await s3_repository.generate_presigned_url(file_key)
    assert "http" in presigned_url
    assert file_key in presigned_url

    async with aiohttp.ClientSession() as session:
        async with session.put(
            URL(presigned_url, encoded=True),
            data=file_content,
        ) as response:
            assert response.status in (200, 204)

    downloaded_content = await s3_repository.get_file(file_key)
    assert downloaded_content == file_content

    await s3_repository.delete_file(file_key)
    with pytest.raises(Exception):
        await s3_repository.get_file(file_key)


@pytest.mark.asyncio
async def test_s3_stat_returns_object_metadata(s3_repository: S3StorageRepository) -> None:
    file_content = b"metadata-check"
    file_key = f"test_folder/{uuid.uuid4()}.txt"

    await s3_repository.upload_file(
        content=file_content,
        key=file_key,
        content_type="text/plain",
    )

    obj_stat = await s3_repository.stat(file_key)
    assert obj_stat["key"] == file_key
    assert obj_stat["size"] == len(file_content)
    assert obj_stat["etag"] is not None
    assert obj_stat["content_type"] in ("text/plain", "binary/octet-stream", "application/octet-stream")

    await s3_repository.delete_file(file_key)


@pytest.mark.asyncio
async def test_s3_list_returns_objects_by_prefix(s3_repository: S3StorageRepository) -> None:
    prefix = f"test_list/{uuid.uuid4()}"
    key_one = f"{prefix}/one.txt"
    key_two = f"{prefix}/two.txt"
    other_key = f"other/{uuid.uuid4()}.txt"

    await s3_repository.upload_file(b"one", key_one, "text/plain")
    await s3_repository.upload_file(b"two", key_two, "text/plain")
    await s3_repository.upload_file(b"other", other_key, "text/plain")

    listed = await s3_repository.list(prefix=prefix)
    listed_keys = {item["key"] for item in listed}
    assert key_one in listed_keys
    assert key_two in listed_keys
    assert other_key not in listed_keys

    limited = await s3_repository.list(prefix=prefix, limit=1)
    assert len(limited) == 1

    await s3_repository.delete_file(key_one)
    await s3_repository.delete_file(key_two)
    await s3_repository.delete_file(other_key)


@pytest.mark.asyncio
async def test_s3_update_metadata_replaces_custom_metadata(s3_repository: S3StorageRepository) -> None:
    file_key = f"test_folder/{uuid.uuid4()}.txt"
    await s3_repository.upload_file(
        content=b"metadata-update",
        key=file_key,
        content_type="text/plain",
    )

    updated = await s3_repository.update_metadata(
        key=file_key,
        metadata={"source": "pytest", "owner": "rag-service"},
        content_type="text/plain",
    )

    metadata = updated["metadata"]
    assert metadata.get("source") == "pytest"
    assert metadata.get("owner") == "rag-service"

    await s3_repository.delete_file(file_key)
