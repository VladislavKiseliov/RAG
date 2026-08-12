from __future__ import annotations

import uuid
from typing import Any

from rag_service.application.document_service import DataBaseDocumentService
from rag_service.application.models import UploadLinkResult
from rag_service.domain.document import IngestionDocument
from rag_service.domain.errors.postgres import DocumentNotFound
from rag_service.domain.errors.storage import StorageNotFoundError
from rag_service.infrastructures.providers.bucket_storage_provider import BucketStorageProvider
from rag_service.infrastructures.providers.vector_storage_provider import VectorStorageProvider
from rag_service.utils.logger_config import setup_logger

logger = setup_logger(__name__)


class DocumentOrchestrator:
    def __init__(self,
                 s3_storage : BucketStorageProvider,
                 vector_storage : VectorStorageProvider,
                 database : DataBaseDocumentService):

        self.s3_storage = s3_storage
        self.vector_storage = vector_storage
        self.database = database

    async def get_upload_link(self, filename: str, file_size: int) -> UploadLinkResult:
        doc = IngestionDocument.create_new(filename=filename, file_size=file_size)

        await self.database.create_doc(
            doc_id=doc.id,
            filename=doc.filename,
            s3key=doc.s3key,
            file_size=doc.file_size,
        )

        presigned_url = await self.s3_storage.generate_presigned_url(doc.s3key)

        return UploadLinkResult(
            doc_id=str(doc.id),
            presigned_url=presigned_url,
        )

    async def delete_document(self, doc_id: uuid.UUID, key: str | None = None):
        """Шаг 3: Полная очистка"""
        document = await self.database.get_document_by_id(doc_id)
        if document is None:
            raise DocumentNotFound(str(doc_id))

        object_key = key or document.s3key

        # Файл в S3 может отсутствовать по причинам, не связанным с самим документом
        # (кто-то вручную почистил бакет, пропущенный шаг миграции и т.п.) - раньше это
        # ПОЛНОСТЬЮ блокировало удаление: stat() падал, delete_document кидал 404, а
        # запись в Postgres/Qdrant оставалась "осиротевшей" навсегда, без способа её
        # убрать через UI. Удаление - это про очистку ЗАПИСИ о документе, а не про
        # обязательное наличие файла: если файла и так уже нет, удалять из S3 нечего,
        # но БД/Qdrant всё равно должны быть очищены.
        if object_key:
            try:
                await self.s3_storage.stat(object_key)
                await self.s3_storage.delete_file(object_key)
            except StorageNotFoundError:
                logger.warning(
                    "delete_document: file '%s' already absent in storage for doc_id=%s, "
                    "skipping S3 delete and cleaning up DB/Qdrant anyway", object_key, doc_id,
                )

        # Производные артефакты ingestion (full.md, chapters/*.md, tables/*.csv|html,
        # meta/*.md) заливаются под тем же префиксом {doc_id}/, что и исходный файл
        # (см. IngestionDocument.create_new и IngestionService._store_docling_artifacts),
        # но раньше не удалялись вообще - только object_key выше. Утечка объектов в
        # MinIO с каждым удалённым документом (см. B10 в ISSUES.md). object_key мог
        # уже попасть в этот список - повторный delete_file на уже удалённый ключ в S3
        # идемпотентен, не ошибка.
        artifacts = await self.s3_storage.list(prefix=str(doc_id))
        for artifact in artifacts:
            await self.s3_storage.delete_file(artifact["key"])

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

    async def get_file_url(self, doc_id: uuid.UUID) -> str | None:
        """Presigned inline-viewable URL for a document's original file — powers
        "Открыть исходник" в читалке (iframe, а не принудительный download)."""
        document = await self.database.get_document_by_id(doc_id)
        if document is None or not document.s3key:
            return None
        return await self.s3_storage.generate_presigned_download_url(
            document.s3key, filename=document.filename
        )

    async def get_document_info(self, doc_id: str) -> dict[str, Any]:
        parsed_doc_id = uuid.UUID(doc_id)
        info = await self.database.get_document_full_info(parsed_doc_id)
        if info is None:
            raise DocumentNotFound(doc_id)
        return info





















