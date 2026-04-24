import pytest
import uuid

from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository
from rag_service.settings import settings  # Или пропиши конфиг руками для теста


@pytest.fixture
async def s3_repository():
    """Фикстура для создания репозитория перед тестом."""
    repo = S3StorageRepository(
        endpoint_url="http://localhost:9000",
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket="test-bucket",  # Используем отдельный бакет для тестов!
        secure=False
    )
    return repo


@pytest.mark.asyncio
async def test_s3_upload_and_download(s3_repository):
    # Данные для теста
    file_content = b"Hello, RAG world!"
    file_key = f"test_folder/{uuid.uuid4()}.txt"

    # 1. Тестируем загрузку
    await s3_repository.upload_file(
        content=file_content,
        key=file_key,
        content_type="text/plain"
    )

    # 2. Тестируем получение (get_file)
    downloaded_content = await s3_repository.get_file(file_key)
    assert downloaded_content == file_content

    # 3. Тестируем получение ссылки (presigned url)
    url = await s3_repository.generate_presigned_url(file_key)
    print(url)
    assert "http" in url
    assert file_key in url

    # # 4. Тестируем удаление
    # await s3_repository.delete_file(file_key)
    #
    # # Проверяем, что файла больше нет (зависит от реализации stat или list)
    # # Если get_file после удаления кидает ошибку - это тоже тест
    # with pytest.raises(Exception):
    #     await s3_repository.get_file(file_key)


@pytest.mark.asyncio
async def test_s3_upload_and_download(s3_repository):
    pass