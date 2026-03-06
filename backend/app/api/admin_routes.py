from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from backend.app.sevices.scripts import get_db
    from backend.app.sevices.security import oauth2_scheme
except ModuleNotFoundError:
    from app.sevices.scripts import get_db
    from app.sevices.security import oauth2_scheme


router = APIRouter(prefix="/admin", tags=["admin"])

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
FLOWER_URL = os.getenv("FLOWER_URL", "http://localhost:5555")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
QDRANT_COLLECTION = os.getenv("COLLECTION_NAME") or os.getenv("QDRANT_COLLECTION") or "rag_documents_collection"
MINIO_PUBLIC_BASE = os.getenv("MINIO_PUBLIC_BASE", "http://localhost:9000")


class BlockUserRequest(BaseModel):
    is_blocked: bool


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _ensure_admin_flags_table(db: Session) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS users_shema.admin_user_flags (
              user_id uuid PRIMARY KEY REFERENCES users_shema.users(id) ON DELETE CASCADE,
              is_blocked boolean NOT NULL DEFAULT false,
              updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
    )
    db.commit()


def _is_user_blocked(db: Session, user_id: uuid.UUID) -> bool:
    _ensure_admin_flags_table(db)
    row = db.execute(
        text("SELECT is_blocked FROM users_shema.admin_user_flags WHERE user_id=:user_id"),
        {"user_id": str(user_id)},
    ).first()
    return bool(row[0]) if row else False


def require_admin_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid subject")

    row = db.execute(
        text("SELECT id, login, created_at FROM users_shema.users WHERE id = :id"),
        {"id": str(user_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=401, detail="User not found")

    if _is_user_blocked(db, user_id):
        raise HTTPException(status_code=403, detail="User is blocked")

    if row.login != ADMIN_LOGIN:
        raise HTTPException(status_code=403, detail="Admin access required")

    return {"id": str(row.id), "login": row.login}


@router.get("/stats")
def admin_stats(
    _: dict[str, Any] = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    docs_total = _safe_int(db.execute(text("SELECT count(*) FROM rag_kernel.documents")).scalar())
    docs_7d = _safe_int(
        db.execute(
            text("SELECT count(*) FROM rag_kernel.documents WHERE created_at >= now() - interval '7 days'")
        ).scalar()
    )
    users_total = _safe_int(db.execute(text("SELECT count(*) FROM users_shema.users")).scalar())
    users_7d = _safe_int(
        db.execute(
            text("SELECT count(*) FROM users_shema.users WHERE created_at >= now() - interval '7 days'")
        ).scalar()
    )
    chats_total = _safe_int(db.execute(text("SELECT count(*) FROM users_shema.chats")).scalar())
    chats_7d = _safe_int(
        db.execute(
            text("SELECT count(*) FROM users_shema.chats WHERE created_at >= now() - interval '7 days'")
        ).scalar()
    )

    activity_rows = db.execute(
        text(
            """
            WITH days AS (
              SELECT generate_series(
                date_trunc('day', now()) - interval '6 day',
                date_trunc('day', now()),
                interval '1 day'
              )::date AS day
            ),
            d AS (
              SELECT date_trunc('day', created_at)::date AS day, count(*) AS c
              FROM rag_kernel.documents
              WHERE created_at >= now() - interval '7 days'
              GROUP BY 1
            ),
            m AS (
              SELECT date_trunc('day', created_at)::date AS day, count(*) AS c
              FROM users_shema.messages
              WHERE created_at >= now() - interval '7 days' AND role = 'user'
              GROUP BY 1
            )
            SELECT to_char(days.day, 'DD.MM') AS day, COALESCE(d.c, 0) AS documents, COALESCE(m.c, 0) AS messages
            FROM days
            LEFT JOIN d ON d.day = days.day
            LEFT JOIN m ON m.day = days.day
            ORDER BY days.day
            """
        )
    ).all()

    tasks_active = 0
    try:
        with httpx.Client(timeout=4.0) as client:
            response = client.get(f"{FLOWER_URL.rstrip('/')}/api/tasks")
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                tasks_active = len([x for x in data.values() if x.get("state") == "ACTIVE"])
    except Exception:
        tasks_active = 0

    return {
        "documents_total": docs_total,
        "documents_delta_7d": docs_7d,
        "users_total": users_total,
        "users_delta_7d": users_7d,
        "chats_total": chats_total,
        "chats_delta_7d": chats_7d,
        "tasks_active": tasks_active,
        "activity_7d": [
            {"day": row.day, "documents": _safe_int(row.documents), "messages": _safe_int(row.messages)}
            for row in activity_rows
        ],
    }


@router.get("/documents/stats")
def admin_documents_stats(
    _: dict[str, Any] = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    rows = db.execute(
        text("SELECT status::text AS status, count(*)::int AS c FROM rag_kernel.documents GROUP BY status")
    ).all()
    result = {"completed": 0, "processing": 0, "error": 0}
    for row in rows:
        if row.status in result:
            result[row.status] = _safe_int(row.c)
    result["total"] = result["completed"] + result["processing"] + result["error"]
    return result


@router.get("/documents")
def admin_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("uploaded_at"),
    sort_dir: str = Query("desc"),
    _: dict[str, Any] = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    sort_map = {
        "uploaded_at": "d.created_at",
        "filename": "d.filename",
        "status": "d.status::text",
    }
    order_field = sort_map.get(sort_by, "d.created_at")
    order_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"

    where_parts: list[str] = []
    params: dict[str, Any] = {}

    if status and status in {"completed", "processing", "error"}:
        where_parts.append("d.status::text = :status")
        params["status"] = status
    if search and len(search.strip()) >= 2:
        where_parts.append("d.filename ILIKE :search")
        params["search"] = f"%{search.strip()}%"

    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    offset = (page - 1) * page_size
    params.update({"limit": page_size, "offset": offset})

    total = _safe_int(
        db.execute(text(f"SELECT count(*) FROM rag_kernel.documents d {where_sql}"), params).scalar()
    )

    rows = db.execute(
        text(
            f"""
            SELECT
              d.id::text AS doc_id,
              d.filename,
              d.status::text AS status,
              d.created_at AS uploaded_at,
              d.file_hash,
              COALESCE(pc.chunk_count, 0) AS chunk_count,
              COALESCE((d.meta->>'size_mb')::numeric, 0) AS size_mb
            FROM rag_kernel.documents d
            LEFT JOIN (
              SELECT doc_id, count(*)::int AS chunk_count
              FROM rag_kernel.parent_chunks
              GROUP BY doc_id
            ) pc ON pc.doc_id = d.id
            {where_sql}
            ORDER BY {order_field} {order_dir}
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).all()

    pages = max(1, (total + page_size - 1) // page_size)
    return {
        "items": [
            {
                "doc_id": row.doc_id,
                "filename": row.filename,
                "status": row.status,
                "chunk_count": _safe_int(row.chunk_count),
                "uploaded_at": row.uploaded_at,
                "size_mb": _safe_float(row.size_mb),
            }
            for row in rows
        ],
        "page": page,
        "pages": pages,
        "total": total,
        "page_size": page_size,
    }


@router.get("/documents/{doc_id}")
def admin_document_detail(
    doc_id: str,
    _: dict[str, Any] = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT
              d.id::text AS doc_id,
              d.filename,
              d.status::text AS status,
              d.created_at AS uploaded_at,
              d.file_hash,
              d.meta,
              COALESCE(pc.chunk_count, 0) AS chunk_count
            FROM rag_kernel.documents d
            LEFT JOIN (
              SELECT doc_id, count(*)::int AS chunk_count
              FROM rag_kernel.parent_chunks
              GROUP BY doc_id
            ) pc ON pc.doc_id = d.id
            WHERE d.id = CAST(:doc_id AS uuid)
            """
        ),
        {"doc_id": doc_id},
    ).first()

    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    meta = row.meta or {}
    return {
        "doc_id": row.doc_id,
        "filename": row.filename,
        "status": row.status,
        "chunk_count": _safe_int(row.chunk_count),
        "uploaded_at": row.uploaded_at,
        "size_mb": _safe_float(meta.get("size_mb", 0)),
        "minio_key": meta.get("minio_key"),
        "file_hash": row.file_hash,
        "embedding_model": meta.get("embedding_model", os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")),
        "collection": os.getenv("COLLECTION_NAME") or os.getenv("QDRANT_COLLECTION") or "rag_documents_collection",
        "error_text": meta.get("error"),
    }


@router.post("/documents/{doc_id}/reindex")
def admin_document_reindex(
    doc_id: str,
    _: dict[str, Any] = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.execute(
        text("SELECT status::text AS status, meta FROM rag_kernel.documents WHERE id = CAST(:doc_id AS uuid)"),
        {"doc_id": doc_id},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if row.status != "error":
        raise HTTPException(status_code=400, detail="Reindex is allowed only for error documents")

    db.execute(
        text(
            """
            UPDATE rag_kernel.documents
            SET status='processing', meta = COALESCE(meta, '{}'::jsonb) - 'error'
            WHERE id = CAST(:doc_id AS uuid)
            """
        ),
        {"doc_id": doc_id},
    )
    db.commit()
    return {"doc_id": doc_id, "status": "processing"}


@router.delete("/documents/{doc_id}")
def admin_document_delete(
    doc_id: str,
    _: dict[str, Any] = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    doc = db.execute(
        text("SELECT id::text AS doc_id FROM rag_kernel.documents WHERE id = CAST(:doc_id AS uuid)"),
        {"doc_id": doc_id},
    ).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/delete?wait=true",
                json={
                    "filter": {
                        "must": [{"key": "doc_id", "match": {"value": doc_id}}]
                    }
                },
            )
    except Exception:
        # keep deleting from SQL even if qdrant is not reachable
        pass

    db.execute(
        text("DELETE FROM rag_kernel.documents WHERE id = CAST(:doc_id AS uuid)"),
        {"doc_id": doc_id},
    )
    db.commit()
    return {"status": "deleted", "doc_id": doc_id}


@router.get("/documents/{doc_id}/download")
def admin_document_download(
    doc_id: str,
    _: dict[str, Any] = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = db.execute(
        text("SELECT filename, meta FROM rag_kernel.documents WHERE id = CAST(:doc_id AS uuid)"),
        {"doc_id": doc_id},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    meta = row.meta or {}
    minio_key = meta.get("minio_key") or f"documents/{doc_id}/{row.filename}"
    return {
        "url": f"{MINIO_PUBLIC_BASE.rstrip('/')}/{minio_key}",
        "expires_in": 900,
    }


@router.get("/users")
def admin_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None),
    status: str | None = Query(None),
    sort_by: str = Query("registered_at"),
    sort_dir: str = Query("desc"),
    _: dict[str, Any] = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_admin_flags_table(db)

    sort_map = {
        "registered_at": "u.created_at",
        "username": "u.login",
        "chats_count": "COALESCE(ch.c,0)",
    }
    order_field = sort_map.get(sort_by, "u.created_at")
    order_dir = "ASC" if sort_dir.lower() == "asc" else "DESC"

    where_parts: list[str] = []
    params: dict[str, Any] = {}
    if search and len(search.strip()) >= 2:
        where_parts.append("u.login ILIKE :search")
        params["search"] = f"%{search.strip()}%"
    if status == "active":
        where_parts.append("COALESCE(f.is_blocked, false) = false")
    elif status == "blocked":
        where_parts.append("COALESCE(f.is_blocked, false) = true")
    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    offset = (page - 1) * page_size
    params.update({"limit": page_size, "offset": offset})

    total = _safe_int(
        db.execute(
            text(
                f"""
                SELECT count(*)
                FROM users_shema.users u
                LEFT JOIN users_shema.admin_user_flags f ON f.user_id = u.id
                {where_sql}
                """
            ),
            params,
        ).scalar()
    )

    rows = db.execute(
        text(
            f"""
            SELECT
              u.id::text AS user_id,
              u.login AS username,
              u.created_at AS registered_at,
              COALESCE(f.is_blocked, false) AS is_blocked,
              COALESCE(ch.c, 0) AS chats_count,
              COALESCE(msg.c, 0) AS messages_count
            FROM users_shema.users u
            LEFT JOIN users_shema.admin_user_flags f ON f.user_id = u.id
            LEFT JOIN (
              SELECT user_id, count(*)::int AS c
              FROM users_shema.chats
              GROUP BY user_id
            ) ch ON ch.user_id = u.id
            LEFT JOIN (
              SELECT c.user_id, count(m.id)::int AS c
              FROM users_shema.messages m
              JOIN users_shema.chats c ON c.chat_id = m.chat_id
              GROUP BY c.user_id
            ) msg ON msg.user_id = u.id
            {where_sql}
            ORDER BY {order_field} {order_dir}
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).all()

    pages = max(1, (total + page_size - 1) // page_size)
    return {
        "items": [
            {
                "user_id": row.user_id,
                "username": row.username,
                "is_blocked": bool(row.is_blocked),
                "registered_at": row.registered_at,
                "chats_count": _safe_int(row.chats_count),
                "messages_count": _safe_int(row.messages_count),
                "documents_count": 0,
            }
            for row in rows
        ],
        "page": page,
        "pages": pages,
        "total": total,
        "page_size": page_size,
    }


@router.get("/users/{user_id}")
def admin_user_detail(
    user_id: str,
    _: dict[str, Any] = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ensure_admin_flags_table(db)
    row = db.execute(
        text(
            """
            SELECT
              u.id::text AS user_id,
              u.login AS username,
              u.created_at AS registered_at,
              COALESCE(f.is_blocked, false) AS is_blocked
            FROM users_shema.users u
            LEFT JOIN users_shema.admin_user_flags f ON f.user_id = u.id
            WHERE u.id = CAST(:user_id AS uuid)
            """
        ),
        {"user_id": user_id},
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")

    stats = db.execute(
        text(
            """
            SELECT
              COALESCE((SELECT count(*) FROM users_shema.chats WHERE user_id = CAST(:user_id AS uuid)), 0) AS chats_count,
              COALESCE((
                SELECT count(m.id)
                FROM users_shema.messages m
                JOIN users_shema.chats c ON c.chat_id = m.chat_id
                WHERE c.user_id = CAST(:user_id AS uuid)
              ), 0) AS messages_count
            """
        ),
        {"user_id": user_id},
    ).first()

    recent_chats = db.execute(
        text(
            """
            SELECT
              c.chat_id::text AS chat_id,
              c.title,
              c.created_at,
              COALESCE(msg.count_messages, 0) AS messages_count,
              COALESCE(msg.last_message_at, c.created_at) AS last_message_at
            FROM users_shema.chats c
            LEFT JOIN (
              SELECT chat_id, count(*)::int AS count_messages, max(created_at) AS last_message_at
              FROM users_shema.messages
              GROUP BY chat_id
            ) msg ON msg.chat_id = c.chat_id
            WHERE c.user_id = CAST(:user_id AS uuid)
            ORDER BY COALESCE(msg.last_message_at, c.created_at) DESC
            LIMIT 5
            """
        ),
        {"user_id": user_id},
    ).all()

    return {
        "user_id": row.user_id,
        "username": row.username,
        "is_blocked": bool(row.is_blocked),
        "registered_at": row.registered_at,
        "chats_count": _safe_int(stats.chats_count),
        "messages_count": _safe_int(stats.messages_count),
        "documents_count": 0,
        "recent_chats": [
            {
                "chat_id": item.chat_id,
                "title": item.title,
                "created_at": item.created_at,
                "messages_count": _safe_int(item.messages_count),
                "last_message_at": item.last_message_at,
            }
            for item in recent_chats
        ],
    }


@router.patch("/users/{user_id}/block")
def admin_user_block(
    user_id: str,
    payload: BlockUserRequest,
    _: dict[str, Any] = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = db.execute(
        text("SELECT id::text AS user_id, login FROM users_shema.users WHERE id = CAST(:id AS uuid)"),
        {"id": user_id},
    ).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.login == ADMIN_LOGIN:
        raise HTTPException(status_code=400, detail="Admin account cannot be blocked")

    _ensure_admin_flags_table(db)
    db.execute(
        text(
            """
            INSERT INTO users_shema.admin_user_flags(user_id, is_blocked, updated_at)
            VALUES (CAST(:user_id AS uuid), :is_blocked, now())
            ON CONFLICT (user_id)
            DO UPDATE SET is_blocked = EXCLUDED.is_blocked, updated_at = now()
            """
        ),
        {"user_id": user_id, "is_blocked": payload.is_blocked},
    )

    if payload.is_blocked:
        db.execute(
            text(
                """
                UPDATE users_shema.refresh_tokens
                SET revoked = true
                WHERE user_id = CAST(:user_id AS uuid) AND revoked = false
                """
            ),
            {"user_id": user_id},
        )
    db.commit()
    return {"status": "ok", "is_blocked": payload.is_blocked}


@router.get("/tasks")
def admin_tasks(
    state: str | None = Query(None),
    _: dict[str, Any] = Depends(require_admin_user),
) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(f"{FLOWER_URL.rstrip('/')}/api/tasks")
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Flower is unavailable: {exc}")

    tasks: list[dict[str, Any]] = []
    if isinstance(data, dict):
        for task_id, task in data.items():
            task_state = task.get("state", "")
            if state and task_state != state:
                continue
            kwargs = task.get("kwargs") or {}
            tasks.append(
                {
                    "task_id": task_id,
                    "filename": kwargs.get("file_path") or kwargs.get("filename"),
                    "status": task_state,
                    "elapsed": task.get("runtime"),
                    "traceback": task.get("traceback"),
                }
            )
    return {"items": tasks}


@router.delete("/tasks/{task_id}")
def admin_cancel_task(
    task_id: str,
    _: dict[str, Any] = Depends(require_admin_user),
) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.post(
                f"{FLOWER_URL.rstrip('/')}/api/task/revoke/{task_id}",
                params={"terminate": "true"},
            )
            response.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to revoke task: {exc}")
    return {"status": "revoked", "task_id": task_id}


def _ping_http(url: str, timeout_seconds: float = 2.0) -> tuple[str, int | None]:
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(url)
        latency = int((time.perf_counter() - start) * 1000)
        if response.status_code >= 500:
            return "offline", latency
        return "online", latency
    except Exception:
        return "offline", None


@router.get("/health")
def admin_health(
    _: dict[str, Any] = Depends(require_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    services: list[dict[str, Any]] = []

    services.append({"name": "backend", "status": "online", "latency_ms": 0})

    rag_health_url = f"{(os.getenv('RAG_SERVICE_URL') or 'http://localhost:8001').rstrip('/')}/health"
    rag_status, rag_latency = _ping_http(rag_health_url, timeout_seconds=3.0)
    services.append({"name": "rag", "status": "degraded" if rag_status == "online" and (rag_latency or 0) > 500 else rag_status, "latency_ms": rag_latency})

    qdrant_status, qdrant_latency = _ping_http(f"{QDRANT_URL}/healthz", timeout_seconds=2.0)
    services.append({"name": "qdrant", "status": "degraded" if qdrant_status == "online" and (qdrant_latency or 0) > 300 else qdrant_status, "latency_ms": qdrant_latency})

    minio_url = f"{MINIO_PUBLIC_BASE.rstrip('/')}/minio/health/live"
    minio_status, minio_latency = _ping_http(minio_url, timeout_seconds=2.0)
    services.append({"name": "minio", "status": "degraded" if minio_status == "online" and (minio_latency or 0) > 200 else minio_status, "latency_ms": minio_latency})

    start = time.perf_counter()
    postgres_status = "online"
    postgres_latency: int | None = None
    try:
        db.execute(text("SELECT 1"))
        postgres_latency = int((time.perf_counter() - start) * 1000)
    except Exception:
        postgres_status = "offline"
    if postgres_status == "online" and (postgres_latency or 0) > 100:
        postgres_status = "degraded"
    services.append({"name": "postgres", "status": postgres_status, "latency_ms": postgres_latency})

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    parsed = urlparse(redis_url)
    redis_host = parsed.hostname or "localhost"
    redis_port = parsed.port or 6379
    redis_status = "online"
    redis_latency: int | None = None
    try:
        import socket

        start = time.perf_counter()
        sock = socket.create_connection((redis_host, redis_port), timeout=1.0)
        redis_latency = int((time.perf_counter() - start) * 1000)
        sock.close()
    except Exception:
        redis_status = "offline"
    if redis_status == "online" and (redis_latency or 0) > 50:
        redis_status = "degraded"
    services.append({"name": "redis", "status": redis_status, "latency_ms": redis_latency})

    return {"services": services, "checked_at": datetime.now(timezone.utc)}


@router.get("/qdrant/stats")
def admin_qdrant_stats(
    _: dict[str, Any] = Depends(require_admin_user),
) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=6.0) as client:
            response = client.get(f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}")
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Qdrant unavailable: {exc}")

    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    vectors_count = _safe_int(result.get("vectors_count"))
    segments_count = _safe_int(result.get("segments_count"))
    disk_size_mb = _safe_float(result.get("disk_data_size", 0)) / (1024 * 1024)

    optimizer_status = "ok"
    status_obj = result.get("status") if isinstance(result, dict) else None
    if isinstance(status_obj, str) and status_obj.lower() not in {"green", "ok"}:
        optimizer_status = "optimizing"

    return {
        "collection": QDRANT_COLLECTION,
        "vectors_count": vectors_count,
        "segments_count": segments_count,
        "disk_data_size_mb": round(disk_size_mb, 2),
        "optimizer_status": optimizer_status,
    }

