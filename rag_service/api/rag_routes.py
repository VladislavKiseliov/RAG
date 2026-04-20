from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from rag_service.api.schemas import (
    DeleteDocumentResponse,
    DocumentDetailResponse,
    DocumentStatusResponse,
    DocumentSummaryResponse,
    PlaceholderActionResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from rag_service.application.document_service import DocumentQueryService, DocumentService
from backend.repository.document_storage_repository import DocumentStorageRepository
from backend.services.document_upload_service import DocumentUploadService
from rag_service.application.ingestion_service import IngestionService
from rag_service.utils.logger_config import setup_logger

logger = setup_logger("rag_service.api")

router = APIRouter(prefix="/documents", tags=["documents"])


def get_retrieve_service(request: Request):
    return request.app.state.retrieve_service


def get_ingestion_service(request: Request) -> IngestionService:
    return request.app.state.ingestion_service


def get_document_service(request: Request) -> DocumentService:
    return request.app.state.document_service


def get_document_query_service(request: Request) -> DocumentQueryService:
    return request.app.state.document_query_service


def get_document_upload_service(request: Request) -> DocumentUploadService:
    from rag_service.workers.task import ingest_document_task

    return DocumentUploadService(
        document_service=request.app.state.document_service,
        storage_repository=DocumentStorageRepository(request.app.state.minio_provider),
        enqueue_ingestion=ingest_document_task.delay,
    )


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(
    body: RetrieveRequest,
    retrieve_service=Depends(get_retrieve_service),
):
    result = await retrieve_service.search(query=body.query, top_k=body.top_k)
    logger.info("Retrieve", extra={"query": body.query, "top_k": body.top_k, "total": result.get("total")})
    return result



@router.get("", response_model=list[DocumentSummaryResponse])
async def list_documents(
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    filename: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    document_query_service: DocumentQueryService = Depends(get_document_query_service),
):
    if not (1 <= limit <= 1000):
        raise HTTPException(400, "limit: from 1 to 1000")
    if offset < 0:
        raise HTTPException(400, "offset cannot be negative")

    docs = await document_query_service.list_documents(
        limit=limit,
        offset=offset,
        status=status,
        filename=filename,
        created_from=created_from,
        created_to=created_to,
    )
    return [
        DocumentSummaryResponse(
            doc_id=str(doc.id),
            filename=doc.filename,
            status=doc.status.value,
            created_at=doc.created_at,
            chunk_count=doc.chunk_count,
        )
        for doc in docs
    ]


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
async def get_document(
    doc_id: str,
    document_query_service: DocumentQueryService = Depends(get_document_query_service),
):
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(400, "Invalid doc_id format")

    doc = await document_query_service.get_document_by_id(doc_uuid)
    if doc is None:
        raise HTTPException(404, "Document not found")

    meta = doc.meta if isinstance(doc.meta, dict) else None
    return DocumentDetailResponse(
        doc_id=str(doc.id),
        filename=doc.filename,
        status=doc.status.value,
        created_at=doc.created_at,
        chunk_count=doc.chunk_count,
        file_hash=doc.file_hash,
        minio_key=doc.minio_key or (meta.get("minio_key") if meta else None),
        meta=meta,
    )


@router.get("/{doc_id}/status", response_model=DocumentStatusResponse)
async def get_status(
    doc_id: str,
    document_query_service: DocumentQueryService = Depends(get_document_query_service),
):
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


@router.delete("/{doc_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    doc_id: str,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    document_query_service: DocumentQueryService = Depends(get_document_query_service),
    document_service: DocumentService = Depends(get_document_service),
):
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(400, "Invalid doc_id format")

    doc = await document_query_service.get_document_by_id(doc_uuid)
    if doc is None:
        raise HTTPException(404, "Document not found")

    await ingestion_service.vector_provider.delete(doc_uuid)
    await document_service.delete_document(doc_uuid)

    return DeleteDocumentResponse(status="deleted", doc_id=str(doc_uuid))


@router.post("/{doc_id}/reingest", response_model=PlaceholderActionResponse, status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def reingest_document(doc_id: str):
    """Placeholder: should enqueue full document re-processing from stored source file."""
    return PlaceholderActionResponse(
        status="not_implemented",
        action="reingest_document",
        detail="Should recreate parent chunks and child vectors for an existing document.",
    )


@router.post("/{doc_id}/reindex", response_model=PlaceholderActionResponse, status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def reindex_document(doc_id: str):
    """Placeholder: should rebuild vector points from already stored parent/child source data."""
    return PlaceholderActionResponse(
        status="not_implemented",
        action="reindex_document",
        detail="Should refresh vector storage without re-uploading the file.",
    )


@router.get("/{doc_id}/chunks", response_model=PlaceholderActionResponse, status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def get_document_chunks(doc_id: str):
    """Placeholder: should expose parent chunks for debugging and admin inspection."""
    return PlaceholderActionResponse(
        status="not_implemented",
        action="get_document_chunks",
        detail="Should return parent chunk content and metadata for one document.",
    )

