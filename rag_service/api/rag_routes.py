from __future__ import annotations

from urllib.parse import unquote_plus
import asyncio
import csv
import io
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Annotated

import httpx
from fastapi import APIRouter, Depends, status, Query, Header, Response, Request
from rag_service.api.schemas import (
    BatchDeleteDocumentsRequest,
    BatchDeleteDocumentsResponse,
    ChapterContentResponse,
    ChapterSummary,
    ChapterTable,
    DeleteDocumentResponse,
    DocumentDetailResponse,
    DocumentStatusResponse,
    DocumentSummaryResponse,
    PlaceholderActionResponse,
    RetrieveRequest,
    RetrieveResponse, TableSummary, UploadFileResponse, MinioWebhookEvent, DocumentStatus,
)
from rag_service.application.task_dispatcher_service import TaskDispatcherService
from rag_service.domain.errors import (
    ChapterNotFound,
    DocumentNotFound,
    DuplicateFilenameError,
    InvalidDocumentIdError,
    ParentChunkNotFound,
    WebhookAuthorizationError,
)
from rag_service.application.ingestion_service import IngestionService
from rag_service.dependencies import DocumentOrchestratorDep, RetrieveServiceDep, TaskDispatcherServiceDep, DocServiceDep, DocQueryServiceDep
from rag_service.utils.logger_config import setup_logger



logger = setup_logger("rag_service.api")

router = APIRouter(tags=["RAG Knowledge Engine"])

# logging.basicConfig(level=logging.DEBUG)
# logging.getLogger("httpx").setLevel(logging.DEBUG)
# logging.getLogger("httpcore").setLevel(logging.DEBUG)
# =============================================================================
# 1. CLIENT API (Поиск и получение знаний для Агента)
# =============================================================================

@router.post("/documents/retrieve", response_model=RetrieveResponse)
async def retrieve(
        body: RetrieveRequest,
        retrieve_service: RetrieveServiceDep,
):
    result = await retrieve_service.retrieve(queries=body.queries, top_k=body.top_k)
    logger.info("Retrieve", extra={"queries_count": len(body.queries), "total": result.get("total")})
    return result


# =============================================================================
# 2. INGESTION API (Жизненный цикл: Загрузка -> Вебхук -> Обработка)
# =============================================================================

@router.post("/documents/ingest/upload-link", response_model=UploadFileResponse)
async def generate_link_upload_file(
        filename: str,
        file_size: int,
        upload_service: DocumentOrchestratorDep
):
    """Шаг 1: Регистрация файла и получение Presigned URL для MinIO"""
    doc = await upload_service.database.get_document_by_filename(filename=filename)
    if doc is not None:
        raise DuplicateFilenameError(filename)

    return await upload_service.get_upload_link(filename, file_size)


@router.post("/documents/ingest/webhook")
async def handle_webhook(
    event: MinioWebhookEvent,
    dispatcher: TaskDispatcherServiceDep,
    authorization: Annotated[str | None, Header(alias="authorization")] = None,
):
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    if token != os.getenv("MINIO_NOTIFY_WEBHOOK_AUTH_TOKEN_1"):
        raise WebhookAuthorizationError()

    # Per-record try/except: одна упавшая запись (например DocumentByStorageKeyNotFound) не должна
    # рвать весь ответ non-200 — иначе MinIO ретраит ВЕСЬ вебхук, и уже успешно задиспатченные
    # записи 1..N-1 продиспатчатся повторно (см. B6 в ISSUES.md; идемпотентность самого диспатча —
    # отдельно в TaskDispatcherService.dispatch_ingestion).
    failed: list[str] = []
    for record in event.records:
        raw_key = record.s3.object.key
        s3key = unquote_plus(raw_key)
        try:
            await dispatcher.dispatch_ingestion(s3key=s3key)
        except Exception:
            logger.exception("Webhook record dispatch failed s3key=%s", s3key)
            failed.append(s3key)

    if failed:
        return {"status": "partial", "failed": failed}

    return {"status": "accepted"}

#
# @router.get("/documents/{doc_id}/status", response_model=DocumentStatusResponse)
# async def get_status(
#         doc_id: str,
#         document_query_service: DocumentQueryService = Depends(get_document_query_service),
# ):
#     """Проверка статуса обработки документа (processing/completed/error)"""
#     try:
#         doc_uuid = uuid.UUID(doc_id)
#     except ValueError:
#         raise HTTPException(400, "Invalid doc_id format")
#
#     doc = await document_query_service.get_document_by_id(doc_uuid)
#     if doc is None:
#         raise HTTPException(404, "Document not found")
#
#     return DocumentStatusResponse(
#         doc_id=str(doc.id),
#         status=doc.status.value,
#         filename=doc.filename,
#         created_at=doc.created_at,
#         chunk_count=doc.chunk_count,
#     )
#
# #
# # =============================================================================
# # 3. MANAGEMENT API (Управление документами и метаданными)
# # =============================================================================
#
@router.get("/documents")
async def list_documents(
        database: DocServiceDep,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        filename: str | None = None,
):
    """Список всех документов в базе с фильтрацией по статусу и названию (ilike)."""
    docs = await database.list_documents(
        limit=limit,
        offset=offset,
        status=status,
        filename=filename,
    )
    return [
        {
            "doc_id": str(d.id),
            "filename": d.filename,
            "status": d.status.value if hasattr(d.status, "value") else str(d.status),
            "created_at": d.created_at.isoformat(),
            "chunk_count": d.chunk_count,
            "s3key": d.s3key,
            "size": d.file_size,
            "has_summary": bool(d.summary),
        }
        for d in docs
    ]


@router.delete("/documents/{doc_id}", response_model=DeleteDocumentResponse)
async def delete_document(
        doc_id: str,
        upload_service: DocumentOrchestratorDep,
):
    """Delete a document from storage, vector DB, and Postgres."""
    try:
        doc_id = uuid.UUID(doc_id)
    except ValueError as exc:
        raise InvalidDocumentIdError() from exc

    try:
        await upload_service.delete_document(doc_id=doc_id)
    except ValueError as exc:
        raise DocumentNotFound(doc_id) from exc

    return DeleteDocumentResponse(status="deleted", doc_id=str(doc_id))

@router.post("/documents/batch-delete", response_model=BatchDeleteDocumentsResponse)
async def batch_delete_documents(
    body: BatchDeleteDocumentsRequest,
    upload_service: DocumentOrchestratorDep,
):
    deleted: list[str] = []
    not_found: list[str] = []
    failed: list[dict[str, str]] = []

    for raw_doc_id in body.doc_ids:
        try:
            parsed_doc_id = uuid.UUID(raw_doc_id)
        except ValueError:
            failed.append({"doc_id": raw_doc_id, "reason": "invalid_doc_id"})
            continue

        try:
            await upload_service.delete_document(doc_id=parsed_doc_id)
            deleted.append(str(parsed_doc_id))
        except ValueError:
            not_found.append(str(parsed_doc_id))
        except Exception as exc:
            failed.append({"doc_id": str(parsed_doc_id), "reason": str(exc)})

    return BatchDeleteDocumentsResponse(
        deleted=deleted,
        not_found=not_found,
        failed=failed,
    )


@router.get("/documents/{doc_id}", response_model=DocumentDetailResponse)
async def get_document_details(
        doc_id: str,
        document_query_service: DocQueryServiceDep,
        document_orchestrator: DocumentOrchestratorDep,
):
    """Полная информация о документе: метаданные, ключ в S3, главы и таблицы"""
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError as exc:
        raise InvalidDocumentIdError() from exc

    doc = await document_query_service.get_document_by_id(doc_uuid)
    if doc is None:
        raise DocumentNotFound(doc_id)

    chapters = await document_query_service.get_chapters_by_doc_id(doc_uuid)
    tables = await document_query_service.get_tables_by_doc_id(doc_uuid)

    # Best-effort: недоступность S3 при генерации presigned-ссылки не должна ронять
    # весь ответ — читалка просто не покажет кнопку "Открыть исходник".
    try:
        file_url = await document_orchestrator.get_file_url(doc_uuid)
    except Exception:
        logger.warning("Failed to generate file_url for doc_id=%s", doc_id, exc_info=True)
        file_url = None

    return DocumentDetailResponse(
        doc_id=str(doc.id),
        filename=doc.filename,
        status=doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        created_at=doc.created_at,
        chunk_count=doc.chunk_count,
        file_hash=doc.file_hash,
        s3key=doc.s3key,
        file_url=file_url,
        meta=doc.meta if isinstance(doc.meta, dict) else {},
        summary=doc.summary,
        chapters=[ChapterSummary(chapter_number=c.chapter_number, title=c.title, summary=c.summary) for c in chapters],
        tables=[TableSummary(table_index=t.table_index) for t in tables],
    )


@router.post("/documents/{doc_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_document(
        doc_id: str,
        task_dispatcher: TaskDispatcherServiceDep,
):
    """Полная переиндексация уже загруженного документа (Docling-парсинг + Qdrant заново)."""
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError as exc:
        raise InvalidDocumentIdError() from exc

    await task_dispatcher.dispatch_reindexing(doc_uuid)
    return {"status": "queued", "doc_id": doc_id}


@router.post("/documents/{doc_id}/summarize", status_code=status.HTTP_202_ACCEPTED)
async def summarize_document(
        doc_id: str,
        task_dispatcher: TaskDispatcherServiceDep,
):
    """Пересобрать саммари глав и документа отдельно, без полной переиндексации."""
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError as exc:
        raise InvalidDocumentIdError() from exc

    await task_dispatcher.dispatch_summarization(doc_uuid)
    return {"status": "queued", "doc_id": doc_id}


_TABLE_LINK_RE = re.compile(r"\[→\s*Таблица\s+(\d+)\]\([^)]*\)")


def _parse_csv_table(csv_bytes: bytes) -> tuple[list[str], list[list[str]]]:
    """Split extracted table CSV bytes into a header row and data rows."""
    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"))))
    if not rows:
        return [], []
    return rows[0], rows[1:]


@router.get("/documents/{doc_id}/chapters/{chapter_idx}", response_model=ChapterContentResponse)
async def get_document_chapter_content(
        doc_id: str,
        chapter_idx: int,
        document_query_service: DocQueryServiceDep,
        document_orchestrator: DocumentOrchestratorDep,
):
    """Полный текст главы и таблицы, встреченные в её тексте.

    `chapter_idx` — позиция главы в списке из `GET /documents/{doc_id}`
    (0-based), а не `chapter_number` (произвольная строка вроде "2.1" от Docling).
    Таблицы для главы находятся по ссылкам `[→ Таблица N](...)`, которые
    `_LinkingTableSerializer` вставляет в markdown в момент извлечения таблицы —
    рассинхрон с `document_tables` невозможен по построению (см. её докстринг).
    """
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError as exc:
        raise InvalidDocumentIdError() from exc

    chapters = await document_query_service.get_chapters_by_doc_id(doc_uuid)
    if chapter_idx < 0 or chapter_idx >= len(chapters):
        raise ChapterNotFound(doc_id, chapter_idx)

    chapter = chapters[chapter_idx]
    text_bytes = await document_orchestrator.get_file_s3_by_s3key(chapter.s3_md_path)
    # Маркер [→ Таблица N] остаётся в тексте — фронт сам расставляет карточки таблиц на его месте,
    # а не одним списком в конце (см. table_index в ChapterTable).
    text = text_bytes.decode("utf-8").strip()

    table_indices = {int(m) for m in _TABLE_LINK_RE.findall(text)}

    tables_out: list[ChapterTable] = []
    if table_indices:
        all_tables = await document_query_service.get_tables_by_doc_id(doc_uuid)
        matched = [t for t in all_tables if t.table_index in table_indices]
        csv_blobs = await asyncio.gather(
            *(document_orchestrator.get_file_s3_by_s3key(t.s3_csv_path) for t in matched)
        )
        for t, csv_bytes in zip(matched, csv_blobs):
            cols, rows = _parse_csv_table(csv_bytes)
            tables_out.append(ChapterTable(table_index=t.table_index, name=t.title or f"Таблица {t.table_index}", cols=cols, rows=rows))

    return ChapterContentResponse(text=text, tables=tables_out)


@router.get("/parent-chunks/{parent_id}")
async def get_parent_chunk_text(
        parent_id: str,
        document_query_service: DocQueryServiceDep,
):
    """Полный текст родительского чанка — источники в истории чата отдаются backend'ом
    без текста (см. ChatService._strip_source_previews), фронт подгружает его лениво
    по наведению на источник через этот роут."""
    try:
        parent_uuid = uuid.UUID(parent_id)
    except ValueError as exc:
        raise InvalidDocumentIdError() from exc

    rows = await document_query_service.get_parent_chunks([parent_uuid])
    if not rows:
        raise ParentChunkNotFound(parent_id)

    return {"text": rows[0].content}

#
# # =============================================================================
# # 4. DEBUG & STORAGE API (Прямой доступ к хранилищу - только для админа)
# # =============================================================================
#
# @router.get("/admin/storage/files")
# async def admin_list_storage_files(
#         upload_service: DocumentOrchestratorDep,
#         prefix: str | None = Query(None),
#         limit: int = 100,
# ) -> dict[str, Any]:
#     """Список сырых объектов в S3 бакете"""
#     items = await upload_service.list_files(prefix=prefix, limit=limit)
#     return {"items": items, "total": len(items)}
#
#
# @router.get("/admin/storage/files/content")
# async def admin_download_file(
#         key: str = Query(..., min_length=1),
#         upload_service: DocumentUploadService = Depends(get_document_upload_service),
# ):
#     """Скачать оригинал файла из S3"""
#     content = await upload_service.get_file(key=key)
#     filename = os.path.basename(key)
#     return Response(
#         content=content,
#         media_type="application/octet-stream",
#         headers={"Content-Disposition": f'attachment; filename="{filename}"'},
#     )
#
#
# # =============================================================================
# # 5. PLACEHOLDERS (Будущий функционал из списка)
# # =============================================================================
#
# @router.get("/documents/{doc_id}/chunks", response_model=PlaceholderActionResponse)
# async def get_document_chunks(doc_id: str):
#     """ПОИСК: Получить список всех родительских чанков документа для инспекции нарезки"""
#     return PlaceholderActionResponse(status="not_implemented", action="get_chunks")
#
#
# @router.post("/documents/{doc_id}/reingest", response_model=PlaceholderActionResponse)
# async def reingest_document(doc_id: str):
#     """MAINTENANCE: Перепарсить существующий файл (смена логики чанкинга)"""
#     return PlaceholderActionResponse(status="not_implemented", action="reingest")
#
#
# @router.patch("/documents/{doc_id}/metadata", response_model=PlaceholderActionResponse)
# async def update_document_metadata(doc_id: str, metadata: dict):
#     """MANAGEMENT: Обновить теги или доп. информацию о документе для фильтрации"""
#     return PlaceholderActionResponse(status="not_implemented", action="update_metadata")
