# test_minio.py (в корне проекта)
import asyncio
from providers.minio_provider import MinioProvider


async def main():
    provider = MinioProvider(
        url="http://localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="rag-documents",
    )

    # 1. Загрузить тестовый файл
    content = b"Hello MinIO - test document content"
    minio_key = "documents/test-123/test.txt"

    print("Uploading...")
    key = await provider.upload(content, minio_key, content_type="text/plain")
    print(f"Uploaded: {key}")

    # 2. Скачать обратно
    print("Downloading...")
    downloaded = await provider.download(minio_key)
    print(f"Downloaded: {downloaded}")

    # 3. Проверить что совпадает
    assert content == downloaded, "Content mismatch!"
    print("OK — content matches")

    # 4. Удалить
    # await provider.delete(minio_key)
    # print("Deleted")


asyncio.run(main())