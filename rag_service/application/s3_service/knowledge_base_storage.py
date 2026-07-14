from __future__ import annotations

from typing import Any

from rag_service.domain.storage import StorageDomain
from rag_service.infrastructures.repositories.s3_storage_repository import S3StorageRepository
from rag_service.settings import settings


class KnowledgeBaseStorageService:
    """S3-хранилище, привязанное к бакету базы знаний.

    Базовый набор методов — то же самое, чем сегодня пользуются
    DocumentOrchestrator/IngestionService. Дальше сюда добавятся операции
    под метаданные и раздельное хранение по главам/таблицам.
    """

    def __init__(self, store: S3StorageRepository) -> None:
        self._store = store
        self._bucket = settings.minio_buckets[StorageDomain.KNOWLEDGE_BASE]

    async def upload_file(self, content: bytes, key: str, content_type: str) -> None:
        await self._store.upload_file(content, key, content_type, bucket=self._bucket)

    async def get_file(self, key: str) -> bytes:
        return await self._store.get_file(key, bucket=self._bucket)

    async def delete_file(self, key: str) -> None:
        await self._store.delete_file(key, bucket=self._bucket)

    async def generate_presigned_url(self, key: str, expiration: int = 300) -> str:
        return await self._store.generate_presigned_url(key, bucket=self._bucket, expiration=expiration)

    async def stat(self, key: str) -> dict[str, Any]:
        return await self._store.stat(key, bucket=self._bucket)

    async def list(self, prefix: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        return await self._store.list(bucket=self._bucket, prefix=prefix, limit=limit)

    async def update_metadata(
        self,
        key: str,
        metadata: dict[str, str],
        content_type: str | None = None,
    ) -> dict[str, Any]:
        return await self._store.update_metadata(
            key, bucket=self._bucket, metadata=metadata, content_type=content_type
        )

    async def ensure_bucket(self) -> None:
        await self._store.ensure_bucket(self._bucket)
