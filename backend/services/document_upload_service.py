from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from hashlib import sha256

from backend.repository.document_storage_repository import DocumentStorageRepository
from rag_service.api.schemas import UploadDocumentResponse
from rag_service.application.document_service import DocumentService
from rag_service.models import DocumentStatus

MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_MIME = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_EXT = (".pdf", ".txt", ".docx")


class DocumentUploadService:
    """Сервис оркестрации загрузки документов и файловых CRUD-операций."""

    def __init__(
        self,
        document_service: DocumentService,
        storage_repository: DocumentStorageRepository,
        enqueue_ingestion: Callable[..., None],
    ) -> None:
        """Создает сервис с зависимостями на метаданные документов, хранилище и постановку задачи ingest."""
        self._document_service = document_service
        self._storage_repository = storage_repository
        self._enqueue_ingestion = enqueue_ingestion

    async def upload_document(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> UploadDocumentResponse:
        """Проверяет файл, сохраняет его в хранилище, регистрирует документ в БД и ставит ingestion-задачу."""
        self._validate_upload_payload(filename=filename, content=content, content_type=content_type)
        file_hash = self._compute_hash(content)
        existing = await self._document_service.get_document_by_hash(file_hash)
        if existing is not None and existing.status != DocumentStatus.error:
            return self._build_duplicate_response(existing)

        doc_id = uuid.uuid4()
        minio_key = self._build_storage_key(doc_id=doc_id, filename=filename)
        await self._store_file(
            content=content,
            minio_key=minio_key,
            content_type=content_type,
        )

        created_id = await self._create_doc_record(
            filename=filename,
            file_hash=file_hash,
            doc_id=doc_id,
            minio_key=minio_key,
            content_type=content_type,
        )

        self._enqueue_ingestion_task(
            doc_id=str(created_id),
            minio_key=minio_key,
            filename=filename,
        )

        return self._build_uploaded_response(
            created_id=created_id,
            filename=filename,
            minio_key=minio_key,
            size=len(content),
        )

    async def get_file(self, *, key: str) -> bytes:
        """Возвращает содержимое файла по ключу из объектного хранилища."""
        return await self._storage_repository.get_file(key)

    async def get_file_metadata(self, *, key: str) -> dict:
        """Возвращает метаданные файла по ключу (размер, etag, content-type и др.)."""
        return await self._storage_repository.get_file_metadata(key)

    async def list_files(self, *, prefix: str | None = None, limit: int | None = None) -> list[dict]:
        """Возвращает список файлов, опционально отфильтрованный по префиксу и ограниченный по количеству."""
        return await self._storage_repository.list_files(prefix=prefix, limit=limit)

    async def delete_file(self, *, key: str) -> dict:
        """Удаляет файл по ключу и возвращает служебный ответ об удалении."""
        await self._storage_repository.delete_file(key)
        return {"status": "deleted", "key": key}

    @staticmethod
    def _validate_upload_payload(*, filename: str, content: bytes, content_type: str | None) -> None:
        """Проверяет расширение, MIME-тип, непустое содержимое и ограничение размера файла."""
        extension = os.path.splitext(filename)[1].lower()
        if not filename or extension not in ALLOWED_EXT:
            raise ValueError("Unsupported file extension")

        if content_type and content_type not in ALLOWED_MIME:
            raise ValueError("Unsupported content type")

        if not content:
            raise ValueError("Empty file")
        if len(content) > MAX_FILE_SIZE:
            raise OverflowError("File too large")

    @staticmethod
    def _compute_hash(content: bytes) -> str:
        """Вычисляет SHA-256 хеш содержимого файла для дедупликации."""
        return sha256(content).hexdigest()

    @staticmethod
    def _build_storage_key(*, doc_id: uuid.UUID, filename: str) -> str:
        """Строит ключ файла в хранилище в формате `documents/{doc_id}/{filename}`."""
        return f"documents/{doc_id}/{filename}"

    async def _store_file(self, *, content: bytes, minio_key: str, content_type: str | None) -> None:
        """Сохраняет файл в объектное хранилище с корректным content-type."""
        await self._storage_repository.upload_file(
            content,
            minio_key,
            content_type=content_type or "application/octet-stream",
        )

    async def _create_doc_record(
        self,
        *,
        filename: str,
        file_hash: str,
        doc_id: uuid.UUID,
        minio_key: str,
        content_type: str | None,
    ) -> uuid.UUID:
        """Создает или обновляет запись документа в БД и возвращает `doc_id`."""
        return await self._document_service.create_doc(
            filename=filename,
            file_hash=file_hash,
            meta={"minio_key": minio_key, "content_type": content_type},
            doc_id=doc_id,
        )

    def _enqueue_ingestion_task(self, *, doc_id: str, minio_key: str, filename: str) -> None:
        """Ставит задачу ingestion в очередь для последующего парсинга и индексации."""
        self._enqueue_ingestion(
            doc_id=doc_id,
            minio_key=minio_key,
            filename=filename,
        )

    @staticmethod
    def _build_duplicate_response(existing) -> UploadDocumentResponse:
        """Формирует ответ API для случая дубликата файла по хешу."""
        return UploadDocumentResponse(
            uploaded=0,
            skipped=1,
            files=[],
            duplicates=[
                {
                    "doc_id": str(existing.id),
                    "filename": existing.filename,
                    "status": existing.status.value,
                    "reason": "duplicate_file_hash",
                }
            ],
        )

    @staticmethod
    def _build_uploaded_response(
        *,
        created_id: uuid.UUID,
        filename: str,
        minio_key: str,
        size: int,
    ) -> UploadDocumentResponse:
        """Формирует успешный ответ API по загруженному файлу."""
        return UploadDocumentResponse(
            uploaded=1,
            skipped=0,
            files=[
                {
                    "doc_id": str(created_id),
                    "filename": filename,
                    "minio_key": minio_key,
                    "size": size,
                    "status": DocumentStatus.processing.value,
                }
            ],
            duplicates=[],
        )
