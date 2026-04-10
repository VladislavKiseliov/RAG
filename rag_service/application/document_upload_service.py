from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from hashlib import sha256

from rag_service.api.schemas import UploadDocumentResponse
from rag_service.application.document_service import DocumentService
from rag_service.infrastructures.providers.minio_provider import MinioProvider
from rag_service.models import DocumentStatus

MAX_FILE_SIZE = 50 * 1024 * 1024
ALLOWED_MIME = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_EXT = (".pdf", ".txt", ".docx")


class DocumentUploadService:
    """Application use case for accepting files and enqueueing ingestion."""

    def __init__(
        self,
        document_service: DocumentService,
        minio_provider: MinioProvider,
        enqueue_ingestion: Callable[..., None],
    ) -> None:
        self._document_service = document_service
        self._minio_provider = minio_provider
        self._enqueue_ingestion = enqueue_ingestion

    async def upload_document(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> UploadDocumentResponse:
        """Validate, store, register, and enqueue one document for ingestion."""
        extension = os.path.splitext(filename)[1].lower()
        if not filename or extension not in ALLOWED_EXT:
            raise ValueError("Unsupported file extension")

        if content_type and content_type not in ALLOWED_MIME:
            raise ValueError("Unsupported content type")

        if not content:
            raise ValueError("Empty file")
        if len(content) > MAX_FILE_SIZE:
            raise OverflowError("File too large")

        file_hash = sha256(content).hexdigest()
        existing = await self._document_service.get_document_by_hash(file_hash)
        if existing is not None and existing.status != DocumentStatus.error:
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

        doc_id = uuid.uuid4()
        minio_key = f"documents/{doc_id}/{filename}"
        await self._minio_provider.upload(
            content,
            minio_key,
            content_type=content_type or "application/octet-stream",
        )

        created_id = await self._document_service.create_doc(
            filename=filename,
            file_hash=file_hash,
            meta={"minio_key": minio_key, "content_type": content_type},
            doc_id=doc_id,
        )

        self._enqueue_ingestion(
            doc_id=str(created_id),
            minio_key=minio_key,
            filename=filename,
        )

        return UploadDocumentResponse(
            uploaded=1,
            skipped=0,
            files=[
                {
                    "doc_id": str(created_id),
                    "filename": filename,
                    "minio_key": minio_key,
                    "size": len(content),
                    "status": DocumentStatus.processing.value,
                }
            ],
            duplicates=[],
        )
