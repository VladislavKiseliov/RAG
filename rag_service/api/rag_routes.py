# rag_service/api/rag_routes.py
from __future__ import annotations

import os
import uuid
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from rag_service.providers.minio_provider import MinioProvider
from rag_service.repositories.document_repository import DocumentRepository
from rag_service.services.ingestion_service import IngestionService
from rag_service.services.task import ingest_document_task
router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE   = 50 * 1024 * 1024
ALLOWED_MIME    = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_EXT     = (".pdf", ".txt", ".docx")


async def _read_file(file: UploadFile, max_bytes: int) -> bytes:
    size, chunks = 0, []
    while data := await file.read(1024 * 1024):
        size += len(data)
        if size > max_bytes:
            raise HTTPException(413, "Файл слишком большой (макс 50MB)")
        chunks.append(data)
    return b"".join(chunks)


def _validate(filename: str, content_type: str | None) -> None:
    if content_type in ALLOWED_MIME:
        return
    if any(filename.lower().endswith(ext) for ext in ALLOWED_EXT):
        return
    raise HTTPException(415, "Разрешены только PDF, TXT, DOCX")


@router.post("/upload-from-disk", status_code=status.HTTP_201_CREATED)
async def upload_from_disk(request: Request):
    """Временный эндпоинт — грузит все файлы из docs/ в MinIO."""

    docs_dir = os.path.join(os.getcwd(), "docs")

    if not os.path.exists(docs_dir):
        raise HTTPException(status_code=404, detail="Директория docs/ не найдена")

    allowed_ext = (".pdf", ".txt", ".docx")
    files = [
        f for f in os.listdir(docs_dir)
        if os.path.isfile(os.path.join(docs_dir, f))
           and f.lower().endswith(allowed_ext)
    ]

    if not files:
        raise HTTPException(status_code=404, detail="Файлы не найдены в docs/")

    minio: MinioProvider = request.app.state.minio_provider
    results = []

    for filename in files:
        file_path = os.path.join(docs_dir, filename)
        with open(file_path, "rb") as f:
            content = f.read()

        doc_id = uuid.uuid4()
        minio_key = f"documents/{doc_id}/{filename}"

        await minio.upload(
            content,
            minio_key,
            content_type="application/pdf",
        )

        results.append({
            "doc_id": str(doc_id),
            "filename": filename,
            "minio_key": minio_key,
            "size": len(content),
        })

        ingest_document_task.delay(
            doc_id=str(doc_id),
            minio_key=minio_key,
            filename=filename,
        )

    return {
        "uploaded": len(results),
        "files": results,
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(request: Request, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "Имя файла обязательно")

    _validate(file.filename, file.content_type)

    content = await _read_file(file, MAX_FILE_SIZE)
    if not content:
        raise HTTPException(400, "Файл пустой")

    service: IngestionService = request.app.state.ingestion_service
    result = await service.ingest_bytes(
        filename=file.filename,
        content=content,
    )

    return {"doc_id": str(result.doc_id), "status": result.status.value}


@router.get("/status/{doc_id}")
async def get_status(doc_id: str, request: Request):
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(400, "Неверный формат doc_id")

    session_factory = request.app.state.ingestion_service._session_factory
    async with session_factory() as session:
        repo = DocumentRepository(session)
        doc  = await repo.get_document_by_id(doc_uuid)
        if doc is None:
            raise HTTPException(404, "Документ не найден")

    return {
        "doc_id":     str(doc.id),
        "status":     doc.status.value,
        "filename":   doc.filename,
        "created_at": doc.created_at,
    }


@router.get("")
async def list_documents(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    filename: str | None = None,
):
    if not (1 <= limit <= 1000):
        raise HTTPException(400, "limit: от 1 до 1000")
    if offset < 0:
        raise HTTPException(400, "offset не может быть отрицательным")

    session_factory = request.app.state.ingestion_service._session_factory
    async with session_factory() as session:
        repo = DocumentRepository(session)
        docs = await repo.list_documents(
            limit=limit, offset=offset,
            status=status, filename=filename,
        )

    return [
        {
            "doc_id":     str(d.id),
            "status":     d.status.value,
            "filename":   d.filename,
            "created_at": d.created_at,
        }
        for d in docs
    ]


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, request: Request):
    try:
        doc_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(400, "Неверный формат doc_id")

    ingestion_service: IngestionService = request.app.state.ingestion_service
    session_factory = ingestion_service._session_factory
    vector_provider = ingestion_service._vector_provider

    async with session_factory() as session:
        repo = DocumentRepository(session)
        if await repo.get_document_by_id(doc_uuid) is None:
            raise HTTPException(404, "Документ не найден")

        async with session.begin():
            await vector_provider.delete(doc_uuid)
            await repo.delete_document(doc_uuid)

    return {"status": "deleted", "doc_id": str(doc_uuid)}
