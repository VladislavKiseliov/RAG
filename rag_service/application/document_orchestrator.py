from __future__ import annotations

import uuid
from typing import Any

from rag_service.api.schemas import UploadFileResponse
from rag_service.application.document_service import DataBaseDocumentService
from rag_service.domain.document import IngestionDocument
from rag_service.domain.errors.storage import StorageNotFoundError
from rag_service.infrastructures.providers.bucket_storage_provider import BucketStorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider


class DocumentOrchestrator:
    def __init__(self,
                 s3_storage : BucketStorageProvider,
                 vector_storage : VectorStorageProvider,
                 database : DataBaseDocumentService):

        self.s3_storage = s3_storage
        self.vector_storage = vector_storage
        self.database = database

    async def get_upload_link(self, filename: str, file_size: int) -> UploadFileResponse:
        doc = IngestionDocument.create_new(filename=filename, file_size=file_size)

        await self.database.create_doc(
            doc_id=doc.id,
            filename=doc.filename,
            s3key=doc.s3key,
            file_size=doc.file_size,
        )

        presigned_url = await self.s3_storage.generate_presigned_url(doc.s3key)

        return UploadFileResponse(
            doc_id=str(doc.id),
            presigned_url=presigned_url,
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
        except StorageNotFoundError:
            raise ValueError(f"File '{object_key}' not found in storage")

        await self.s3_storage.delete_file(object_key)
        await self.vector_storage.delete_by_field("doc_id", str(doc_id))
        await self.database.delete_document(doc_id)

    async def get_list_document(self) -> list[dict[str, Any]]:
        documents = await self.database.list_documents(limit=10_000, offset=0)
        result: list[dict[str, Any]] = []

        for document in documents:
            result.append(
                {
                    "doc_id": str(document.id),
                    "filename": document.filename,
                    "status": getattr(document.status, "value", str(document.status)),
                    "size": document.file_size,
                    "s3key": document.s3key,
                }
            )

        return result

    async def get_file_s3_by_s3key(self, key: str) -> bytes:
        return await self.s3_storage.get_file(key)

    async def get_document_info(self, doc_id: str) -> dict[str, Any]:
        parsed_doc_id = uuid.UUID(doc_id)
        info = await self.database.get_document_full_info(parsed_doc_id)
        if info is None:
            raise ValueError(f"Document '{doc_id}' not found")
        return info





















