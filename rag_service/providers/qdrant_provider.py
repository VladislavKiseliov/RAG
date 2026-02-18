from __future__ import annotations

import os
import uuid
from typing import Any

import asyncio

import httpx

from rag_service.providers.embedding_provider import EmbeddingProvider


class QdrantVectorProvider:
    """Запись векторов в Qdrant через REST API."""

    def __init__(
        self,
        *,
        url: str | None = None,
        collection: str | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        timeout: float = 60.0,
        distance: str = "Cosine",
        embedding_batch_size: int = 64,
        upsert_batch_size: int = 64,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        hnsw_m: int | None = None,
        hnsw_ef_construct: int | None = None,
        optimizers_default_segment_number: int | None = None,
        optimizers_memmap_threshold: int | None = None,
        optimizers_indexing_threshold: int | None = None,
        wal_capacity_mb: int | None = None,
    ) -> None:
        self._url = (url or os.getenv("QDRANT_URL") or "").rstrip("/")
        self._collection = collection or os.getenv("COLLECTION_NAME") or os.getenv("QDRANT_COLLECTION")
        self._embedding_provider = embedding_provider
        self._timeout = timeout
        self._distance = distance
        self._embedding_batch_size = max(1, embedding_batch_size)
        self._upsert_batch_size = max(1, upsert_batch_size)
        self._max_retries = max(0, max_retries)
        self._retry_backoff = max(0.0, retry_backoff)
        self._hnsw_m = hnsw_m
        self._hnsw_ef_construct = hnsw_ef_construct
        self._optimizers_default_segment_number = optimizers_default_segment_number
        self._optimizers_memmap_threshold = optimizers_memmap_threshold
        self._optimizers_indexing_threshold = optimizers_indexing_threshold
        self._wal_capacity_mb = wal_capacity_mb

        if not self._url:
            raise RuntimeError("QDRANT_URL is not set")
        if not self._collection:
            raise RuntimeError("COLLECTION_NAME is not set")
        if self._embedding_provider is None:
            raise RuntimeError("Embedding provider is required")

    async def upsert(self, doc_id: uuid.UUID, chunks: list[str], meta: dict | None) -> None:
        if not chunks:
            return

        vectors: list[list[float]] = []
        for start in range(0, len(chunks), self._embedding_batch_size):
            batch = chunks[start : start + self._embedding_batch_size]
            batch_vectors = await self._embedding_provider.embed(batch)
            if not batch_vectors:
                raise RuntimeError("Embeddings are empty")
            vectors.extend(batch_vectors)

        await self._ensure_collection(len(vectors[0]))

        for start in range(0, len(chunks), self._upsert_batch_size):
            points = []
            end = start + self._upsert_batch_size
            for idx, (chunk, vector) in enumerate(zip(chunks[start:end], vectors[start:end]), start=start):
                payload = {
                    "doc_id": str(doc_id),
                    "chunk_index": idx,
                    "text": chunk,
                }
                if meta:
                    payload["meta"] = meta

                points.append(
                    {
                        "id": f"{doc_id}:{idx}",
                        "vector": vector,
                        "payload": payload,
                    }
                )

            url = f"{self._url}/collections/{self._collection}/points?wait=true"
            await self._request("put", url, json={"points": points})

    async def delete(self, doc_id: uuid.UUID) -> None:
        url = f"{self._url}/collections/{self._collection}/points/delete?wait=true"
        payload = {
            "filter": {
                "must": [
                    {
                        "key": "doc_id",
                        "match": {"value": str(doc_id)},
                    }
                ]
            }
        }
        await self._request("post", url, json=payload)

    async def _ensure_collection(self, vector_size: int) -> None:
        url = f"{self._url}/collections/{self._collection}"
        resp = await self._request("get", url, allow_status={200, 404, 400})
        if resp.status_code == 200:
            return

        create_payload: dict[str, Any] = {
            "vectors": {"size": vector_size, "distance": self._distance}
        }

        hnsw: dict[str, Any] = {}
        if self._hnsw_m is not None:
            hnsw["m"] = self._hnsw_m
        if self._hnsw_ef_construct is not None:
            hnsw["ef_construct"] = self._hnsw_ef_construct
        if hnsw:
            create_payload["hnsw_config"] = hnsw

        optimizers: dict[str, Any] = {}
        if self._optimizers_default_segment_number is not None:
            optimizers["default_segment_number"] = self._optimizers_default_segment_number
        if self._optimizers_memmap_threshold is not None:
            optimizers["memmap_threshold"] = self._optimizers_memmap_threshold
        if self._optimizers_indexing_threshold is not None:
            optimizers["indexing_threshold"] = self._optimizers_indexing_threshold
        if optimizers:
            create_payload["optimizers_config"] = optimizers

        if self._wal_capacity_mb is not None:
            create_payload["wal_config"] = {"wal_capacity_mb": self._wal_capacity_mb}

        await self._request("put", url, json=create_payload)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict | None = None,
        allow_status: set[int] | None = None,
    ) -> httpx.Response:
        allow_status = allow_status or set()
        attempt = 0
        last_exc: Exception | None = None
        while attempt <= self._max_retries:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.request(method, url, json=json)
                if resp.status_code in allow_status or resp.status_code < 500:
                    resp.raise_for_status()
                    return resp
                last_exc = httpx.HTTPStatusError(
                    f"Qdrant server error: {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc

            attempt += 1
            if attempt <= self._max_retries and self._retry_backoff > 0:
                await asyncio.sleep(self._retry_backoff * attempt)

        if last_exc:
            raise last_exc
        raise RuntimeError("Qdrant request failed")
