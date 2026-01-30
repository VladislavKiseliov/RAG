from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis

from ..config import REDIS_URL


_JOBS_LIST_KEY = "ingestion:jobs"
_JOB_KEY_PREFIX = "ingestion:job:"


def _redis_client() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


def add_job(job_id: str, file_path: str, collection: str, metadata: Optional[Dict[str, Any]]) -> None:
    client = _redis_client()
    key = f"{_JOB_KEY_PREFIX}{job_id}"
    payload = {
        "job_id": job_id,
        "file_path": file_path,
        "collection": collection,
        "metadata": json.dumps(metadata) if metadata is not None else "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    client.hset(key, mapping=payload)
    client.lpush(_JOBS_LIST_KEY, job_id)


def get_job(job_id: str) -> Optional[Dict[str, str]]:
    client = _redis_client()
    key = f"{_JOB_KEY_PREFIX}{job_id}"
    data = client.hgetall(key)
    return data or None


def list_job_ids(limit: int = 100, offset: int = 0) -> List[str]:
    if limit <= 0:
        return []
    client = _redis_client()
    start = offset
    end = offset + limit - 1
    return client.lrange(_JOBS_LIST_KEY, start, end)


def count_jobs() -> int:
    client = _redis_client()
    return int(client.llen(_JOBS_LIST_KEY))
