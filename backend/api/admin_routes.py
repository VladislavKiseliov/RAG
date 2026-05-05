from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from backend.dependencies import get_current_user_from_token, get_user_service
from backend.models.database_models import Users
from backend.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["admin"])
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL", "http://rag-service:8001").rstrip("/")


class BlockUserRequest(BaseModel):
    is_blocked: bool


class AdminUserCreateRequest(BaseModel):
    login: str
    password: str


class AdminUserUpdateRequest(BaseModel):
    login: str
    password: str


async def _proxy_rag_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    """Proxy request to RAG service and normalize transport/HTTP errors.

    Args:
        method: Outbound HTTP method.
        path: Target path on RAG service, including leading slash.
        params: Optional query params forwarded to RAG service.
        json_body: Optional JSON payload for outbound request.

    Returns:
        Parsed JSON when response is JSON, plain text otherwise, or None for
        empty responses.

    Raises:
        HTTPException: If RAG service returns non-success status or is
        unreachable.
    """
    url = f"{RAG_SERVICE_URL}{path}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
        try:
            response = await client.request(method=method, url=url, params=params, json=json_body)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail: Any
            try:
                detail = exc.response.json()
            except Exception:
                detail = exc.response.text or "RAG service error"
            raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"RAG service unavailable: {exc}") from exc

    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text


@router.get("/users/repo")
async def admin_users_repo(
    page_size: int = Query(50, ge=1, le=500),
    user_service: UserService = Depends(get_user_service),
) -> dict[str, Any]:
    """Get paginated list of users from repository-backed service layer."""
    return await user_service.get_users_repo(page_size=page_size)


@router.get("/users/repo/{user_id}")
async def admin_user_repo_detail(
    user_id: uuid.UUID,
    user_service: UserService = Depends(get_user_service),
) -> dict[str, Any]:
    """Get single user details by UUID.

    Raises:
        HTTPException: 404 if user is not found.
    """
    user = await user_service.get_user_repo_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/users/repo")
async def admin_user_repo_create(
    payload: AdminUserCreateRequest,
    user_service: UserService = Depends(get_user_service),
) -> dict[str, Any]:
    """Create a new user.

    Raises:
        HTTPException: 409 if login is already in use.
    """
    try:
        return await user_service.create_user_repo(login=payload.login, password=payload.password)
    except ValueError:
        raise HTTPException(status_code=409, detail="User with this login already exists")


@router.put("/users/repo/{user_id}")
async def admin_user_repo_update(
    user_id: uuid.UUID,
    payload: AdminUserUpdateRequest,
    user_service: UserService = Depends(get_user_service),
) -> dict[str, Any]:
    """Update user credentials by UUID.

    Raises:
        HTTPException: 404 if user does not exist.
        HTTPException: 409 if login conflicts with an existing user.
    """
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
    user_service: UserService = Depends(get_user_service),
) -> dict[str, Any]:
    """Delete user by UUID.

    Raises:
        HTTPException: 404 if user does not exist.
    """
    deleted = await user_service.delete_user_repo(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deleted", "user_id": str(user_id)}


@router.get("/documents")
async def admin_documents_list(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    filename: str | None = Query(None),
    created_from: str | None = Query(None),
    created_to: str | None = Query(None),
) -> Any:
    """List documents from RAG service with optional filters and pagination."""
    params = {
        "limit": limit,
        "offset": offset,
        "status": status,
        "filename": filename,
        "created_from": created_from,
        "created_to": created_to,
    }
    clean_params = {k: v for k, v in params.items() if v is not None}
    return await _proxy_rag_request("GET", "/documents", params=clean_params)


@router.post("/documents/upload-link")
async def admin_document_upload_link(
    filename: str = Query(..., min_length=1),
    file_size: int = Query(..., ge=1),
) -> Any:
    """Generate presigned upload link via RAG ingestion API.

    Args:
        filename: Original client file name.
        file_size: File size in bytes.

    Returns:
        RAG response containing document id, storage key, and presigned URL.
    """
    return await _proxy_rag_request(
        "POST",
        "/documents/ingest/upload-link",
        params={"filename": filename, "file_size": file_size},
    )


@router.get("/documents/{doc_id}")
async def admin_document_detail(doc_id: str) -> Any:
    """Get full document details by id from RAG service."""
    return await _proxy_rag_request("GET", f"/documents/{doc_id}")


@router.get("/documents/{doc_id}/status")
async def admin_document_status(doc_id: str) -> Any:
    """Get processing status of a document from RAG service."""
    return await _proxy_rag_request("GET", f"/documents/{doc_id}/status")


@router.delete("/documents/{doc_id}")
async def admin_document_delete(doc_id: str) -> Any:
    """Delete document in RAG domain (metadata, vectors, and storage links)."""
    return await _proxy_rag_request("DELETE", f"/documents/{doc_id}")


@router.post("/documents/{doc_id}/reindex")
async def admin_document_reindex(doc_id: str) -> Any:
    """Trigger document reindex/reingestion in RAG service."""
    return await _proxy_rag_request("POST", f"/documents/{doc_id}/reindex")


@router.get("/documents/{doc_id}/download")
async def admin_document_download(doc_id: str) -> Response:
    """Download original document bytes through backend proxy.

    Flow:
    1. Request document details in RAG service.
    2. Extract object key (`minio_key`).
    3. Request file content by key from RAG storage endpoint.
    4. Return binary response to client.

    Raises:
        HTTPException: 404 when object key is missing.
        HTTPException: 503 when upstream RAG service is unavailable.
    """
    detail = await _proxy_rag_request("GET", f"/documents/{doc_id}")
    minio_key = detail.get("minio_key") if isinstance(detail, dict) else None
    if not minio_key:
        raise HTTPException(status_code=404, detail="Document minio_key not found")

    url = f"{RAG_SERVICE_URL}/documents/storage/files/content"
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
        try:
            res = await client.get(url, params={"key": minio_key})
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text or "RAG download error") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"RAG service unavailable: {exc}") from exc

    headers = {}
    cd = res.headers.get("content-disposition")
    if cd:
        headers["Content-Disposition"] = cd
    return Response(
        content=res.content,
        media_type=res.headers.get("content-type", "application/octet-stream"),
        headers=headers,
    )
