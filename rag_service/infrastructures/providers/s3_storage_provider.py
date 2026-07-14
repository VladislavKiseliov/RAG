from typing import Protocol, runtime_checkable, Any
import uuid


@runtime_checkable
class S3StorageProvider(Protocol):
    """
    Протокол (интерфейс) для низкоуровневого репозитория объектного хранилища.

    Работает с произвольным бакетом, переданным параметром метода —
    один инстанс обслуживает все бакеты. Определяет минимальный набор
    методов для загрузки, скачивания и управления метаданными файлов (S3/MinIO/Local).
    """

    async def upload_file(
            self,
            content: bytes,
            key: str,
            content_type: str,
            bucket: str,
    ) -> None:
        """
        Загружает байты в хранилище под указанным ключом.

        Args:
            content: Содержимое файла в байтах.
            key: Уникальный путь/имя объекта в хранилище.
            content_type: MIME-тип файла (например, 'application/pdf').
            bucket: Целевой бакет.
        """
        ...

    async def get_file(self, key: str, bucket: str) -> bytes:
        """
        Скачивает содержимое файла из хранилища.

        Args:
            key: Ключ (путь) к объекту.
            bucket: Целевой бакет.

        Returns:
            bytes: Содержимое файла.
        """
        ...

    async def delete_file(self, key: str, bucket: str) -> None:
        """
        Удаляет объект из хранилища по ключу.

        Args:
            key: Ключ (путь) к объекту.
            bucket: Целевой бакет.
        """
        ...

    async def generate_presigned_url(self, key: str, bucket: str, expiration: int = 300) -> str:
        """
        Генерирует временную подписанную ссылку для доступа к объекту.

        Args:
            key: Ключ объекта.
            bucket: Целевой бакет.
            expiration: Время жизни ссылки в секундах.

        Returns:
            str: URL для прямого доступа.
        """
        ...

    async def stat(self, key: str, bucket: str) -> dict[str, Any]:
        """
        Получает информацию об объекте (размер, хеш, тип контента).

        Args:
            key: Ключ объекта.
            bucket: Целевой бакет.

        Returns:
            dict: Словарь с метаданными (size, etag, content_type и т.д.).
        """
        ...

    async def list(self, bucket: str, prefix: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Возвращает список объектов в хранилище по префиксу.

        Args:
            bucket: Целевой бакет.
            prefix: Фильтр по началу пути ключа.
            limit: Максимальное количество объектов в ответе.

        Returns:
            list[dict]: Список словарей с информацией об объектах.
        """
        ...

    async def update_metadata(
        self,
        key: str,
        bucket: str,
        metadata: dict[str, str],
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Заменяет метаданные объекта.

        Args:
            key: Ключ объекта.
            bucket: Целевой бакет.
            metadata: Новые метаданные.
            content_type: Опциональная замена content-type.

        Returns:
            dict: Обновлённые метаданные объекта (формат как у `stat`).
        """
        ...

    async def ensure_bucket(self, bucket: str) -> None:
        """
        Проверяет, что бакет существует. Не создаёт его — это забота
        инфраструктуры (docker-compose/minio-init).

        Args:
            bucket: Целевой бакет.
        """
        ...