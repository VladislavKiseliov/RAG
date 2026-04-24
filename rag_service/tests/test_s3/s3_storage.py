import asyncio

from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository






async def main():
    repo = S3StorageRepository(
        endpoint_url="http://localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        bucket="test-bucket",  # Используем отдельный бакет для тестов!
        secure=False
    )
    minio_key = "СТО Газпром 2-1.12-802-2014 Организация пусконаладочных работ.pdf"
    file_bytes = await repo.get_file(minio_key)
    import io
    file_object = io.BytesIO(file_bytes)
    print(file_object)
    with open("готовый_файл.pdf", "wb") as f:
        f.write(file_bytes)



if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())