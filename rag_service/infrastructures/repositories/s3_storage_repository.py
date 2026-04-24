from __future__ import annotations

from contextlib import asynccontextmanager

import aioboto3


class S3StorageRepository:
    """Репозиторий для низкоуровневой работы с объектным хранилищем (MinIO)."""

    def __init__(self,
                 endpoint_url: str,
                 access_key: str,
                 secret_key: str,
                 bucket: str,
                 secure:str = None,):
        self._session = aioboto3.Session()
        self._config = {
            "endpoint_url": endpoint_url,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
        }
        self.bucket = bucket

    @asynccontextmanager
    async def _get_client(self):
        async with self._session.client("s3", **self._config) as client:
            yield client

    async def upload_file(self,
                          content: bytes,
                          key: str,
                          content_type: str):
        """Загружает байты в хранилище."""
        async with self._get_client() as client:
            await client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type
            )

    async def get_file(self, key: str) -> bytes:
        """Скачивает файл из хранилища."""
        async with self._get_client() as client:
            response = await client.get_object(Bucket=self.bucket, Key=key)
            async with response["Body"] as stream:
                return await stream.read()

    async def delete_file(self, key: str):
        """Удаляет объект из хранилища."""
        async with self._get_client() as client:
            await client.delete_object(Bucket=self.bucket, Key=key)

    async def generate_presigned_url(self, key: str, expiration: int = 300) -> str:
        """Генерирует временную ссылку для прямой загрузки (PUT)."""
        async with self._get_client() as client:
            return await client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expiration
            )
    async def stat(self, minio_key: str) -> dict:
        stat = await self._client.stat_object(
            bucket_name=self._bucket,
            object_name=minio_key,
        )
        return {
            "key": minio_key,
            "size": getattr(stat, "size", None),
            "etag": getattr(stat, "etag", None),
            "last_modified": getattr(stat, "last_modified", None),
            "content_type": getattr(stat, "content_type", None),
            "metadata": getattr(stat, "metadata", None),
        }

    async def update_metadata(self):
        pass

    async def list(self, prefix: str | None = None, limit: int | None = None) -> list[dict]:
        await self.ensure_bucket()
        objects = self._client.list_objects(
            bucket_name=self._bucket,
            prefix=prefix or "",
            recursive=True,
        )
        result: list[dict] = []
        async for obj in objects:
            result.append(
                {
                    "key": getattr(obj, "object_name", None),
                    "size": getattr(obj, "size", None),
                    "etag": getattr(obj, "etag", None),
                    "last_modified": getattr(obj, "last_modified", None),
                    "content_type": getattr(obj, "content_type", None),
                }
            )
            if limit is not None and len(result) >= limit:
                break
        return result







