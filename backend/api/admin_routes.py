from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.dependencies import get_container, get_user_service
from backend.infrastructure import BackendContainer
from backend.repository.document_storage_repository import DocumentStorageRepository
from backend.services.user_service import UserService
from backend.services.document_upload_service import DocumentUploadService
from rag_service.api.schemas import UploadDocumentResponse
from rag_service.application.document_service import DocumentService



router = APIRouter(prefix="/admin", tags=["admin"])


class BlockUserRequest(BaseModel):
    is_blocked: bool


class AdminUserCreateRequest(BaseModel):
    login: str
    password: str


class AdminUserUpdateRequest(BaseModel):
    login: str
    password: str



def _build_minio_provider():
    from rag_service.infrastructures.providers.minio_provider import MinioProvider

    return MinioProvider(
        url=os.getenv("MINIO_URL") or os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        bucket=os.getenv("MINIO_BUCKET", "documents"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )


def get_admin_document_upload_service(
    request: Request,
    container: BackendContainer = Depends(get_container),
) -> DocumentUploadService:
    from rag_service.workers.task import ingest_document_task

    return DocumentUploadService(
        document_service=DocumentService(container.session_factory),
        storage_repository=DocumentStorageRepository(_build_minio_provider()),
        enqueue_ingestion=ingest_document_task.delay,
    )


@router.get("/users/repo")
async def admin_users_repo(
    page_size: int = Query(50, ge=1, le=500),
    _: dict[str, Any] = Depends(require_admin_user),
    user_service: UserService = Depends(get_user_service),
) -> dict[str, Any]:
    return await user_service.get_users_repo(page_size=page_size)


@router.get("/users/repo/{user_id}")
async def admin_user_repo_detail(
    user_id: uuid.UUID,
    _: dict[str, Any] = Depends(require_admin_user),
    user_service: UserService = Depends(get_user_service),
) -> dict[str, Any]:
    user = await user_service.get_user_repo_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/users/repo")
async def admin_user_repo_create(
    payload: AdminUserCreateRequest,
    _: dict[str, Any] = Depends(require_admin_user),
    user_service: UserService = Depends(get_user_service),
) -> dict[str, Any]:
    try:
        return await user_service.create_user_repo(login=payload.login, password=payload.password)
    except ValueError:
        raise HTTPException(status_code=409, detail="User with this login already exists")


@router.put("/users/repo/{user_id}")
async def admin_user_repo_update(
    user_id: uuid.UUID,
    payload: AdminUserUpdateRequest,
    _: dict[str, Any] = Depends(require_admin_user),
    user_service: UserService = Depends(get_user_service),
) -> dict[str, Any]:
    try:
        user = await user_service.update_user_repo(
            user_id=user_id,
            login=payload.login,
            password=payload.password,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="User with this login already exists")
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/users/repo/{user_id}")
async def admin_user_repo_delete(
    user_id: uuid.UUID,
    _: dict[str, Any] = Depends(require_admin_user),
    user_service: UserService = Depends(get_user_service),
) -> dict[str, Any]:
    deleted = await user_service.delete_user_repo(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted", "user_id": str(user_id)}


@router.post("/documents/upload", response_model=UploadDocumentResponse, status_code=status.HTTP_201_CREATED)
async def admin_upload_document(
    file: UploadFile = File(...),
    _: dict[str, Any] = Depends(require_admin_user),
    upload_service: DocumentUploadService = Depends(get_admin_document_upload_service),
):
    try:
        content = await file.read()
        return await upload_service.upload_document(
            filename=file.filename or "",
            content=content,
            content_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc


@router.get("/documents/storage/files")
async def admin_list_storage_files(
    prefix: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=1000),
    _: dict[str, Any] = Depends(require_admin_user),
    upload_service: DocumentUploadService = Depends(get_admin_document_upload_service),
) -> dict[str, Any]:
    items = await upload_service.list_files(prefix=prefix, limit=limit)
    return {"items": items, "total": len(items)}


@router.get("/documents/storage/files/metadata")
async def admin_get_storage_file_metadata(
    key: str = Query(..., min_length=1),
    _: dict[str, Any] = Depends(require_admin_user),
    upload_service: DocumentUploadService = Depends(get_admin_document_upload_service),
) -> dict[str, Any]:
    return await upload_service.get_file_metadata(key=key)


@router.get("/documents/storage/files/content")
async def admin_get_storage_file_content(
    key: str = Query(..., min_length=1),
    _: dict[str, Any] = Depends(require_admin_user),
    upload_service: DocumentUploadService = Depends(get_admin_document_upload_service),
) -> Response:
    content = await upload_service.get_file(key=key)
    filename = os.path.basename(key) or "file.bin"
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/documents/storage/files")
async def admin_delete_storage_file(
    key: str = Query(..., min_length=1),
    _: dict[str, Any] = Depends(require_admin_user),
    upload_service: DocumentUploadService = Depends(get_admin_document_upload_service),
) -> dict[str, Any]:
    return await upload_service.delete_file(key=key)


















