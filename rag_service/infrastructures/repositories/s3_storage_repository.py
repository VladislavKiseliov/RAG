from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import aioboto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from rag_service.domain.errors.storage import (
    StorageDeleteError,
    StorageMetadataError,
    StorageReadError,
    StorageWriteError,
)


class S3StorageRepository:
    """Repository for low-level object storage operations (S3/MinIO)."""

    def __init__(
        self,
        private_endpoint_url: str,
        public_endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: str | None = None,
    ) -> None:
        """
        Initialize a storage repository bound to a single bucket.

        Args:
            private_endpoint_url: S3-compatible endpoint URL (for example MinIO).
            public_endpoint_url: S3-compatible endpoint URL for external downloads.
            access_key: Access key (AWS access key ID format).
            secret_key: Secret key (AWS secret access key format).
            bucket: Target bucket name.
            secure: Compatibility parameter. Kept for constructor stability.
        """
        self._session = aioboto3.Session()
        self._config = {
            "endpoint_url": private_endpoint_url,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "config": Config(signature_version="s3v4"),
        }
        self.bucket = bucket

        # If public URL is not provided, use internal one.
        self._public_cfg = {
            **self._config,
            "endpoint_url": public_endpoint_url
        }

    @asynccontextmanager
    async def _get_client(self):
        """
        Yield an aioboto3 S3 client configured for this repository.

        Yields:
            Configured aioboto3 S3 client instance.
        """
        async with self._session.client("s3", **self._config) as client:
            yield client

    @asynccontextmanager
    async def _get_public_client(self):
        async with self._session.client("s3", **self._public_cfg) as client:
            yield client


    async def upload_file(self, content: bytes, key: str, content_type: str) -> None:
        """
        Upload raw bytes to object storage.

        Args:
            content: File content in bytes.
            key: Object key inside the bucket.
            content_type: MIME type to store with the object.
        """
        try:
            async with self._get_client() as client:
                await client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=content,
                    ContentType=content_type,
                )
        except (ClientError, BotoCoreError) as exc:
            raise StorageWriteError(f"Failed to upload object '{key}'") from exc

    async def get_file(self, key: str) -> bytes:
        """
        Download object bytes from storage.

        Args:
            key: Object key inside the bucket.

        Returns:
            File content as bytes.
        """
        try:
            async with self._get_client() as client:
                response = await client.get_object(Bucket=self.bucket, Key=key)
                async with response["Body"] as stream:
                    return await stream.read()
        except (ClientError, BotoCoreError) as exc:
            raise StorageReadError(f"Failed to download object '{key}'") from exc

    async def delete_file(self, key: str) -> None:
        """
        Delete an object from storage.

        Args:
            key: Object key inside the bucket.
        """
        try:
            async with self._get_client() as client:
                await client.delete_object(Bucket=self.bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise StorageDeleteError(f"Failed to delete object '{key}'") from exc

    async def generate_presigned_url(self, key: str, expiration: int = 300) -> str:
        """
        Generate a presigned PUT URL for direct client upload.

        Args:
            key: Target object key.
            expiration: URL lifetime in seconds.

        Returns:
            Presigned URL.
        """
        try:
            async with self._get_public_client() as client:
                return await client.generate_presigned_url(
                    "put_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=expiration,
                )
        except (ClientError, BotoCoreError) as exc:
            raise StorageMetadataError(f"Failed to generate presigned URL for '{key}'") from exc

    async def stat(self, key: str) -> dict[str, Any]:
        """
        Fetch object metadata via HEAD request.

        Args:
            key: Object key inside the bucket.

        Returns:
            Normalized metadata dictionary.
        """
        try:
            async with self._get_client() as client:
                head = await client.head_object(Bucket=self.bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise StorageMetadataError(f"Failed to read metadata for '{key}'") from exc

        return {
            "key": key,
            "size": head.get("ContentLength"),
            "etag": head.get("ETag"),
            "last_modified": head.get("LastModified"),
            "content_type": head.get("ContentType"),
            "metadata": head.get("Metadata", {}),
        }

    async def update_metadata(
        self,
        key: str,
        metadata: dict[str, str],
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Replace object metadata in-place using server-side copy.

        Args:
            key: Object key inside the bucket.
            metadata: Metadata map to write.
            content_type: Optional content type override. If omitted,
                current object content type is preserved.

        Returns:
            Updated object metadata (same shape as `stat`).
        """
        try:
            async with self._get_client() as client:
                current = await client.head_object(Bucket=self.bucket, Key=key)
                await client.copy_object(
                    Bucket=self.bucket,
                    Key=key,
                    CopySource={"Bucket": self.bucket, "Key": key},
                    Metadata=metadata,
                    MetadataDirective="REPLACE",
                    ContentType=content_type or current.get("ContentType", "application/octet-stream"),
                )
        except (ClientError, BotoCoreError) as exc:
            raise StorageMetadataError(f"Failed to update metadata for '{key}'") from exc
        return await self.stat(key)

    async def list(self, prefix: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """
        List objects by optional prefix.

        Args:
            prefix: Optional key prefix filter.
            limit: Optional maximum number of returned objects.

        Returns:
            List of object descriptors.
        """
        result: list[dict[str, Any]] = []
        token: str | None = None

        try:
            async with self._get_client() as client:
                while True:
                    request: dict[str, Any] = {
                        "Bucket": self.bucket,
                        "Prefix": prefix or "",
                        "MaxKeys": 1000,
                    }
                    if token is not None:
                        request["ContinuationToken"] = token

                    page = await client.list_objects_v2(**request)

                    for obj in page.get("Contents", []):
                        result.append(
                            {
                                "key": obj.get("Key"),
                                "size": obj.get("Size"),
                                "etag": obj.get("ETag"),
                                "last_modified": obj.get("LastModified"),
                            }
                        )
                        if limit is not None and len(result) >= limit:
                            return result

                    if not page.get("IsTruncated"):
                        break
                    token = page.get("NextContinuationToken")
        except (ClientError, BotoCoreError) as exc:
            raise StorageMetadataError("Failed to list objects") from exc

        return result
