from __future__ import annotations

import io
from miniopy_async import Minio


class MinioProvider:
    """Upload/download/list/stat/delete objects in MinIO."""

    def __init__(
        self,
        url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ) -> None:
        host = url.replace("http://", "").replace("https://", "")
        self._client = Minio(
            host,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket = bucket

    async def ensure_bucket(self) -> None:
        exists = await self._client.bucket_exists(self._bucket)
        if not exists:
            await self._client.make_bucket(self._bucket)

    async def upload(
        self,
        content: bytes,
        minio_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
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
        response = await self._client.get_object(
            bucket_name=self._bucket,
            object_name=minio_key,
        )
        return await response.read()

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

    async def delete(self, minio_key: str) -> None:
        await self._client.remove_object(
            bucket_name=self._bucket,
            object_name=minio_key,
        )
