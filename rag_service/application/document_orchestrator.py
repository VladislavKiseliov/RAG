from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from rag_service.api.schemas import UploadFileResponse, DocumentStatus
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.domain.errors import UploadValidationError
from rag_service.infrastructures.providers.s3_storage_provider import S3StorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider


class DocumentOrchestrator:
    def __init__(self,
                 s3_storage : S3StorageProvider,
                 vector_storage : VectorStorageProvider,
                 database : DataBaseDocumentService):

        self.s3_storage = s3_storage
        self.vector_storage = vector_storage
        self.database = database

    async def get_upload_link(self, filename: str,file_size:int) -> UploadFileResponse:
        """Шаг 1: Только подготовка. Мы еще не видели файл."""

        # 1. Валидация только по расширению (так как байтов нет)
        self._validate_metadata(filename,file_size)

        # 2. Генерируем ID
        doc_id = uuid.uuid4()
        key = self._build_object_key(filename = filename,doc_id = doc_id)

        # 3. Создаем запись со статусом загрузки
        await self.database.create_doc(
            doc_id=doc_id,
            filename=filename,
            s3key=key,
        )

        # 4. Получаем ссылку для ПРЯМОЙ загрузки (Client -> MinIO)
        presigned_url = await self.s3_storage.generate_presigned_url(key)

        return UploadFileResponse(
            doc_id=str(doc_id),
            presigned_url=presigned_url
        )

    async def delete_document(self, doc_id: uuid.UUID, key: str | None = None):
        """Шаг 3: Полная очистка"""
        document = await self.database.get_document_by_id(doc_id)
        if document is None:
            raise ValueError(f"Document '{doc_id}' not found")

        object_key = key or document.s3key
        if not object_key:
            raise ValueError(f"Storage key for document '{doc_id}' is empty")

        try:
            await self.s3_storage.stat(object_key)
        except Exception as exc:
            raise ValueError(f"File '{object_key}' not found in storage") from exc

        await self.s3_storage.delete_file(object_key)
        await self.vector_storage.delete_points(doc_id)
        await self.database.delete_document(doc_id)

    async def get_list_document(self) -> list[dict[str, Any]]:
        documents = await self.database.list_documents(limit=10_000, offset=0)
        result: list[dict[str, Any]] = []

        for document in documents:
            key = document.s3key
            if not key and isinstance(document.meta, dict):
                key = document.meta.get("s3key")

            size: int | None = None
            if key:
                try:
                    meta = await self.s3_storage.stat(key)
                    size = meta.get("size")
                except Exception:
                    size = None

            result.append(
                {
                    "doc_id": str(document.id),
                    "filename": document.filename,
                    "status": getattr(document.status, "value", str(document.status)),
                    "size": size,
                    "s3key": key,
                }
            )

        return result

    async def get_file(self, key: str) -> bytes:
        return await self.s3_storage.get_file(key)

    async def get_document_info(self, doc_id: str) -> dict[str, Any]:
        parsed_doc_id = uuid.UUID(doc_id)
        info = await self.database.get_document_full_info(parsed_doc_id)
        if info is None:
            raise ValueError(f"Document '{doc_id}' not found")
        return info


    def _validate_metadata(self, filename: str, file_size: int):
        """Валидация без загрузки файла в память."""
        ALLOWED_EXT = (".pdf", ".docx", ".txt")
        MAX_SIZE = 50 * 1024 * 1024  # 50 MB

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXT:
            raise UploadValidationError(f"Расширение {ext} не поддерживается.")

        if file_size > MAX_SIZE:
            raise UploadValidationError(f"Файл слишком велик ({file_size} байт). Лимит 50МБ.")

        if file_size <= 0:
            raise UploadValidationError("Файл пустой.")

    @staticmethod
    def _compute_hash(content: bytes) -> str:
        return sha256(content).hexdigest()

    @staticmethod
    def _build_object_key(filename:str,doc_id: uuid.UUID) -> str:
        name, ext = os.path.splitext(filename)
        now = datetime.now(timezone.utc)
        return f"documents/{now:%Y/%m}/{doc_id}{ext.lower()}"



















