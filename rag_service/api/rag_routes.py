from __future__ import annotations

import asyncio
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_service.services.ingestion_service import IngestionResult, IngestionService
from rag_service.repositories.document_repository import DocumentRepository
from rag_service.providers.vector_provider import NullVectorProvider
from rag_service.providers.qdrant_provider import QdrantVectorProvider
from rag_service.providers.hf_embedding_provider import HuggingFaceEmbeddingProvider
from rag_service.db.session import create_engine, create_session_factory
from rag_service.models import DocumentStatus


def _to_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None

router = APIRouter(prefix="/documents", tags=["rag"])

MAX_FILE_SIZE = 50 * 1024 * 1024
SMALL_FILE_THRESHOLD = 2 * 1024 * 1024
ALLOWED_MIME = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _derive_async_db_url() -> str:
    db_url = os.getenv("RAG_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL or RAG_DATABASE_URL is not set")
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url
    if db_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + db_url[len("postgresql://") :]
    if db_url.startswith("postgres://"):
        return "postgresql+asyncpg://" + db_url[len("postgres://") :]
    raise RuntimeError("Unsupported database URL scheme")


_async_engine = create_engine(_derive_async_db_url())
_session_factory: async_sessionmaker[AsyncSession] = create_session_factory(_async_engine)
def _build_vector_provider():
    qdrant_url = os.getenv("QDRANT_URL")
    collection = os.getenv("COLLECTION_NAME") or os.getenv("QDRANT_COLLECTION")
    if qdrant_url and collection and os.getenv("HF_TOKEN") and os.getenv("EMBEDDING_MODEL_NAME"):
        embedding = HuggingFaceEmbeddingProvider()
        return QdrantVectorProvider(
            url=qdrant_url,
            collection=collection,
            embedding_provider=embedding,
            embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "64")),
            upsert_batch_size=int(os.getenv("QDRANT_UPSERT_BATCH_SIZE", "64")),
            max_retries=int(os.getenv("QDRANT_MAX_RETRIES", "3")),
            retry_backoff=float(os.getenv("QDRANT_RETRY_BACKOFF", "0.5")),
            hnsw_m=_to_int(os.getenv("QDRANT_HNSW_M")),
            hnsw_ef_construct=_to_int(os.getenv("QDRANT_HNSW_EF_CONSTRUCT")),
            optimizers_default_segment_number=_to_int(os.getenv("QDRANT_OPTIMIZERS_DEFAULT_SEGMENT_NUMBER")),
            optimizers_memmap_threshold=_to_int(os.getenv("QDRANT_OPTIMIZERS_MEMMAP_THRESHOLD")),
            optimizers_indexing_threshold=_to_int(os.getenv("QDRANT_OPTIMIZERS_INDEXING_THRESHOLD")),
            wal_capacity_mb=_to_int(os.getenv("QDRANT_WAL_CAPACITY_MB")),
        )
    return NullVectorProvider()


_vector_provider = _build_vector_provider()
_ingestion_service = IngestionService(_session_factory, _vector_provider)


async def _read_upload_file(file: UploadFile, max_bytes: int) -> bytes:
    size = 0
    chunks: list[bytes] = []
    while True:
        data = await file.read(1024 * 1024)
        if not data:
            break
        size += len(data)
        if size > max_bytes:
            raise HTTPException(status_code=413, detail="File слишком большой")
        chunks.append(data)
    return b"".join(chunks)


def _schedule_ingestion(
    *,
    background_tasks: BackgroundTasks,
    filename: str,
    content: bytes,
    content_type: str | None,
    meta: dict | None,
    doc_id: uuid.UUID,
) -> None:
    async def _run() -> None:
        await _ingestion_service.ingest_bytes(
            filename=filename,
            content=content,
            content_type=content_type,
            meta=meta,
            doc_id=doc_id,
        )

    background_tasks.add_task(asyncio.create_task, _run())


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail="Unsupported file type")

    content = await _read_upload_file(file, MAX_FILE_SIZE)
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    file_hash = _ingestion_service.calculate_file_hash(content)

    async with _session_factory() as session:
        repo = DocumentRepository(session)
        existing = await repo.get_document_by_hash(file_hash)
        if existing is not None:
            if existing.status != DocumentStatus.error:
                return {
                    "doc_id": str(existing.id),
                    "status": existing.status.value,
                }

    doc_id = uuid.uuid4()

    if len(content) > SMALL_FILE_THRESHOLD:
        _schedule_ingestion(
            background_tasks=background_tasks,
            filename=file.filename,
            content=content,
            content_type=file.content_type,
            meta=None,
            doc_id=doc_id,
        )
        return {"doc_id": str(doc_id), "status": DocumentStatus.processing.value}

    result: IngestionResult = await _ingestion_service.ingest_bytes(
        filename=file.filename,
        content=content,
        content_type=file.content_type,
        meta=None,
        doc_id=doc_id,
    )
    return {"doc_id": str(result.doc_id), "status": result.status.value}


@router.get("/status/{doc_id}")
async def get_document_status(doc_id: str):
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document id")

    async with _session_factory() as session:
        repo = DocumentRepository(session)
        doc = await repo.get_document_by_id(doc_uuid)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return {
            "doc_id": str(doc.id),
            "status": doc.status.value,
            "filename": doc.filename,
            "created_at": doc.created_at,
        }


@router.get("")
async def list_documents(
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    filename: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="Invalid limit")
    if offset < 0:
        raise HTTPException(status_code=400, detail="Invalid offset")

    async with _session_factory() as session:
        repo = DocumentRepository(session)
        rows = await repo.list_documents(
            limit=limit,
            offset=offset,
            status=status,
            filename=filename,
            created_from=created_from,
            created_to=created_to,
        )
        return [
            {
                "doc_id": str(doc.id),
                "status": doc.status.value,
                "filename": doc.filename,
                "created_at": doc.created_at,
                "file_hash": doc.file_hash,
            }
            for doc in rows
        ]


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document id")

    async with _session_factory() as session:
        repo = DocumentRepository(session)
        doc = await repo.get_document_by_id(doc_uuid)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")

        tx = await session.begin()
        try:
            await _vector_provider.delete(doc_uuid)
            await repo.delete_document(doc_uuid)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            if tx.is_active:
                await tx.rollback()

    return {"status": "deleted", "doc_id": str(doc_uuid)}
