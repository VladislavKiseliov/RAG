from __future__ import annotations


import Minio



class DocumentStorageRepository:
    """Репозиторий операций с файлами в объектном хранилище."""

    def __init__(self,url:str,access_key:str,secret_key:str,secure:str,bucket:str) -> None:
        """Инициализирует репозиторий с провайдером хранилища."""
        host = url.replace("http://", "").replace("https://", "")
        self._minio_provider = Minio(
            host,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket = bucket


    async def upload_file(self, content: bytes, key: str, content_type: str) -> None:
        """Загружает файл в хранилище по ключу `key`."""
        await self._minio_provider.upload(content, key, content_type=content_type)

    async def get_file(self, key: str) -> bytes:
        """Возвращает содержимое файла по ключу `key`."""
        return await self._minio_provider.download(key)

    async def get_file_metadata(self, key: str) -> dict:
        """Возвращает метаданные файла (размер, etag, даты, metadata) по ключу."""
        return await self._minio_provider.stat(key)

    async def list_files(self, prefix: str | None = None, limit: int | None = None) -> list[dict]:
        """Возвращает список файлов, опционально отфильтрованный по `prefix` и ограниченный `limit`."""
        return await self._minio_provider.list(prefix=prefix, limit=limit)

    async def delete_file(self, key: str) -> None:
        """Удаляет файл из хранилища по ключу `key`."""
        await self._minio_provider.delete(key)
