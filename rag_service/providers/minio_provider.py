# rag_service/providers/minio_provider.py
from __future__ import annotations

import io
from miniopy_async import Minio


class MinioProvider:
    """Загрузка и скачивание файлов из MinIO."""

    def __init__(
        self,
        url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ) -> None:
        # убираем http:// — minio клиент принимает только host:port
        host = url.replace("http://", "").replace("https://", "")
        self._client = Minio(
            host,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket = bucket

    async def ensure_bucket(self) -> None:
        """Создаёт bucket если не существует."""
        exists = await self._client.bucket_exists(self._bucket)
        if not exists:
            await self._client.make_bucket(self._bucket)

    async def upload(
        self,
        content: bytes,
        minio_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Загружает файл в MinIO. Возвращает minio_key."""
        await self.ensure_bucket()
        await self._client.put_object(
            bucket_name=self._bucket,
            object_name=minio_key,
            data=io.BytesIO(content),
            length=len(content),
            content_type=content_type,
        )
        return minio_key

    async def download(self, minio_key: str) -> bytes:
        """Скачивает файл из MinIO. Возвращает bytes."""
        response = await self._client.get_object(
            bucket_name=self._bucket,
            object_name=minio_key,
        )
        return await response.read()

    async def delete(self, minio_key: str) -> None:
        """Удаляет файл из MinIO."""
        await self._client.remove_object(
            bucket_name=self._bucket,
            object_name=minio_key,
        )