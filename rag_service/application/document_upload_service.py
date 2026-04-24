from __future__ import annotations

import os
import uuid
from hashlib import sha256
from typing import Any, Coroutine

from rag_service.api.schemas import UploadFileResponse, DocumentStatus
from rag_service.application.document_service import DataBaseDocumentService
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
        key = f"documents/{doc_id}/{filename}"

        # 3. Создаем запись со статусом загрузки
        await self.database.create_doc(
            doc_id=doc_id,
            filename=filename,
            metadata={"minio_key": key}
        )

        # 4. Получаем ссылку для ПРЯМОЙ загрузки (Client -> MinIO)
        presigned_url = await self.s3_storage.generate_presigned_url(key)

        return UploadFileResponse(
            status_doc=DocumentStatus.processing,
            doc_id=str(doc_id),
            presigned_url=presigned_url
        )

    async def delete_document(self, doc_id: str, key: str):
        """Шаг 3: Полная очистка"""
        await self.storage.delete_file(key)
        await self.vector_storage.delete_vectors_by_id(doc_id)

    async def update_metadata_document(self):
        pass

    async def get_list_document(self):
        pass

    async def get_file(self,key: str)-> Coroutine[Any, Any, bytes]:
        return self.s3_storage.get_file(key)


    def _validate_metadata(self, filename: str, file_size: int):
        """Валидация без загрузки файла в память."""
        ALLOWED_EXT = (".pdf", ".docx", ".txt")
        MAX_SIZE = 50 * 1024 * 1024  # 50 MB

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXT:
            raise ValueError(f"Расширение {ext} не поддерживается.")

        if file_size > MAX_SIZE:
            raise ValueError(f"Файл слишком велик ({file_size} байт). Лимит 50МБ.")

        if file_size <= 0:
            raise ValueError("Файл пустой.")

    @staticmethod
    def _compute_hash(content: bytes) -> str:
        return sha256(content).hexdigest()



















