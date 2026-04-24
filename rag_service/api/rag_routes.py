from __future__ import annotations

import os
import uuid
from typing import Any, Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Response, Request
from rag_service.api.schemas import (
    DeleteDocumentResponse,
    DocumentDetailResponse,
    DocumentStatusResponse,
    DocumentSummaryResponse,
    PlaceholderActionResponse,
    RetrieveRequest,
    RetrieveResponse, UploadFileResponse, MinioWebhookEvent,
)
# Импорты сервисов (предполагаем наличие соответствующих провайдеров)
from rag_service.application.document_service import DocumentQueryService
from rag_service.application.task_dispatcher_service import TaskDispatcherService
from rag_service.workers.ingestion_service import IngestionService
from rag_service.dependencies import RAGServiceDep, RetrieveServiceDep, TaskDispatcherServiceDep
from rag_service.utils.logger_config import setup_logger

logger = setup_logger("rag_service.api")

router = APIRouter(tags=["RAG Knowledge Engine"])


# =============================================================================
# 1. CLIENT API (Поиск и получение знаний для Агента)
# =============================================================================

@router.post("/documents/retrieve", response_model=RetrieveResponse)
async def retrieve(
        body: RetrieveRequest,
        retrieve_service: RetrieveServiceDep,
):
    """Основной поиск по базе знаний (Hybrid Search)"""
    result = await retrieve_service.search(query=body.query, top_k=body.top_k)
    logger.info("Retrieve", extra={"query": body.query, "top_k": body.top_k, "total": result.get("total")})
    return result


# =============================================================================
# 2. INGESTION API (Жизненный цикл: Загрузка -> Вебхук -> Обработка)
# =============================================================================

@router.post("/documents/ingest/upload-link", response_model=UploadFileResponse)
async def generate_link_upload_file(
        filename: str,
        file_size: int,
        upload_service: RAGServiceDep
):
    """Шаг 1: Регистрация файла и получение Presigned URL для MinIO"""
    return await upload_service.get_upload_link(filename, file_size)


@router.post("/documents/ingest/webhook")
async def handle_minio_webhook(
        event: MinioWebhookEvent,
        task_dispatcher :TaskDispatcherServiceDep,
        x_minio_extract_token: Annotated[str | None, Header(alias="X-Minio-Extract-Token")] = None,
):
    """Шаг 2: Сигнал от MinIO о завершении загрузки. Инициирует задачу в Celery."""
    # WEBHOOK_TOKEN должен быть в конфиге
    if x_minio_extract_token != os.getenv("MINIO_WEBHOOK_TOKEN"):
        raise HTTPException(status_code=401, detail="Invalid notification token")

    for record in event.records:
        key = record.s3.object.key
        parts = key.split("/")
        if len(parts) >= 2:
            try:
                doc_id = uuid.UUID(parts[1])
                await task_dispatcher.dispatch_ingestion(doc_id=doc_id, minio_key=key)
            except (ValueError, IndexError):
                logger.warning(f"Could not extract UUID from key: {key}")

    return {"status": "accepted"}


@router.get("/documents/{doc_id}/status", response_model=DocumentStatusResponse)
async def get_status(
        doc_id: str,
        document_query_service: DocumentQueryService = Depends(get_document_query_service),
):
    """Проверка статуса обработки документа (processing/completed/error)"""
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(400, "Invalid doc_id format")

    doc = await document_query_service.get_document_by_id(doc_uuid)
    if doc is None:
        raise HTTPException(404, "Document not found")

    return DocumentStatusResponse(
        doc_id=str(doc.id),
        status=doc.status.value,
        filename=doc.filename,
        created_at=doc.created_at,
        chunk_count=doc.chunk_count,
    )


# =============================================================================
# 3. MANAGEMENT API (Управление документами и метаданными)
# =============================================================================

@router.get("/documents", response_model=list[DocumentSummaryResponse])
async def list_documents(
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        filename: str | None = None,
        document_query_service: DocumentQueryService = Depends(get_document_query_service),
):
    """Список всех документов в базе с фильтрацией"""
    docs = await document_query_service.list_documents(
        limit=limit,
        offset=offset,
        status=status,
        filename=filename
    )
    return [
        DocumentSummaryResponse(
            doc_id=str(doc.id),
            filename=doc.filename,
            status=doc.status.value,
            created_at=doc.created_at,
            chunk_count=doc.chunk_count,
        ) for doc in docs
    ]


@router.get("/documents/{doc_id}", response_model=DocumentDetailResponse)
async def get_document_details(
        doc_id: str,
        document_query_service: DocumentQueryService = Depends(get_document_query_service),
):
    """Полная информация о документе, включая метаданные и ключ в S3"""
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(400, "Invalid doc_id format")

    doc = await document_query_service.get_document_by_id(doc_uuid)
    if doc is None:
        raise HTTPException(404, "Document not found")

    meta = doc.meta if isinstance(doc.meta, dict) else {}
    return DocumentDetailResponse(
        doc_id=str(doc.id),
        filename=doc.filename,
        status=doc.status.value,
        created_at=doc.created_at,
        chunk_count=doc.chunk_count,
        file_hash=doc.file_hash,
        minio_key=doc.minio_key or meta.get("minio_key"),
        meta=meta,
    )


@router.delete("/documents/{doc_id}", response_model=DeleteDocumentResponse)
async def delete_document(
        doc_id: str,
        ingestion_service: IngestionService = Depends(get_ingestion_service),
        document_query_service: DocumentQueryService = Depends(get_document_query_service),
        document_service: DocumentService = Depends(get_document_service),
        upload_service: DocumentUploadService = Depends(get_document_upload_service)
):
    """Полное удаление документа из всех систем (DB, S3, Qdrant)"""
    doc_uuid = uuid.UUID(doc_id)
    doc = await document_query_service.get_document_by_id(doc_uuid)
    if not doc:
        raise HTTPException(404, "Not found")

    # 1. Удаляем векторы
    await ingestion_service.vector_provider.delete(doc_uuid)
    # 2. Удаляем файл из S3
    if doc.minio_key:
        await upload_service.delete_file(key=doc.minio_key)
    # 3. Удаляем запись из БД
    await document_service.delete_document(doc_uuid)

    return DeleteDocumentResponse(status="deleted", doc_id=str(doc_uuid))


# =============================================================================
# 4. DEBUG & STORAGE API (Прямой доступ к хранилищу - только для админа)
# =============================================================================

@router.get("/admin/storage/files")
async def admin_list_storage_files(
        upload_service: RAGServiceDep,
        prefix: str | None = Query(None),
        limit: int = 100,
) -> dict[str, Any]:
    """Список сырых объектов в S3 бакете"""
    items = await upload_service.list_files(prefix=prefix, limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/admin/storage/files/content")
async def admin_download_file(
        key: str = Query(..., min_length=1),
        upload_service: DocumentUploadService = Depends(get_document_upload_service),
):
    """Скачать оригинал файла из S3"""
    content = await upload_service.get_file(key=key)
    filename = os.path.basename(key)
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =============================================================================
# 5. PLACEHOLDERS (Будущий функционал из списка)
# =============================================================================

@router.get("/documents/{doc_id}/chunks", response_model=PlaceholderActionResponse)
async def get_document_chunks(doc_id: str):
    """ПОИСК: Получить список всех родительских чанков документа для инспекции нарезки"""
    return PlaceholderActionResponse(status="not_implemented", action="get_chunks")


@router.post("/documents/{doc_id}/reingest", response_model=PlaceholderActionResponse)
async def reingest_document(doc_id: str):
    """MAINTENANCE: Перепарсить существующий файл (смена логики чанкинга)"""
    return PlaceholderActionResponse(status="not_implemented", action="reingest")


@router.patch("/documents/{doc_id}/metadata", response_model=PlaceholderActionResponse)
async def update_document_metadata(doc_id: str, metadata: dict):
    """MANAGEMENT: Обновить теги или доп. информацию о документе для фильтрации"""
    return PlaceholderActionResponse(status="not_implemented", action="update_metadata")