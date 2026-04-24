from typing import Protocol, runtime_checkable, Any
import uuid


@runtime_checkable
class S3StorageProvider(Protocol):
    """
    Протокол (интерфейс) для работы с объектным хранилищем.

    Определяет минимальный набор методов для загрузки, скачивания
    и управления метаданными файлов (S3/MinIO/Local).
    """

    async def upload_file(
            self,
            content: bytes,
            key: str,
            content_type: str
    ) -> None:
        """
        Загружает байты в хранилище под указанным ключом.

        Args:
            content: Содержимое файла в байтах.
            key: Уникальный путь/имя объекта в хранилище.
            content_type: MIME-тип файла (например, 'application/pdf').
        """
        ...

    async def get_file(self, key: str) -> bytes:
        """
        Скачивает содержимое файла из хранилища.

        Args:
            key: Ключ (путь) к объекту.

        Returns:
            bytes: Содержимое файла.
        """
        ...

    async def delete_file(self, key: str) -> None:
        """
        Удаляет объект из хранилища по ключу.

        Args:
            key: Ключ (путь) к объекту.
        """
        ...

    async def generate_presigned_url(self, key: str, expiration: int = 300) -> str:
        """
        Генерирует временную подписанную ссылку для доступа к объекту.

        Args:
            key: Ключ объекта.
            expiration: Время жизни ссылки в секундах.

        Returns:
            str: URL для прямого доступа.
        """
        ...

    async def stat(self, key: str) -> dict[str, Any]:
        """
        Получает информацию об объекте (размер, хеш, тип контента).

        Args:
            key: Ключ объекта.

        Returns:
            dict: Словарь с метаданными (size, etag, content_type и т.д.).
        """
        ...

    async def list(self, prefix: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Возвращает список объектов в хранилище по префиксу.

        Args:
            prefix: Фильтр по началу пути ключа.
            limit: Максимальное количество объектов в ответе.

        Returns:
            list[dict]: Список словарей с информацией об объектах.
        """
        ...