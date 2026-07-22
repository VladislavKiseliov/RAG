from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class BucketStorageProvider(Protocol):
    """
    Протокол для сервиса хранения, привязанного к одному бакету.

    В отличие от S3StorageProvider (низкоуровневый репозиторий, бакет —
    параметр каждого метода), реализации этого протокола сами знают,
    с каким бакетом работают, и не принимают его снаружи.
    """

    async def upload_file(self, content: bytes, key: str, content_type: str) -> None:
        ...

    async def get_file(self, key: str) -> bytes:
        ...

    async def delete_file(self, key: str) -> None:
        ...

    async def generate_presigned_url(self, key: str, expiration: int = 300) -> str:
        ...

    async def generate_presigned_download_url(
        self, key: str, *, expiration: int = 300, filename: str | None = None
    ) -> str:
        ...

    async def stat(self, key: str) -> dict[str, Any]:
        ...

    async def list(self, prefix: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        ...

    async def update_metadata(
        self,
        key: str,
        metadata: dict[str, str],
        content_type: str | None = None,
    ) -> dict[str, Any]:
        ...

    async def ensure_bucket(self) -> None:
        ...
