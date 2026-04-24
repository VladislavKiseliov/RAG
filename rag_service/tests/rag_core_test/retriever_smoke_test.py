"""Standalone retriever smoke test without starting FastAPI service."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Allow direct run: python rag_service/rag_core_test/retriever_smoke_test.py
if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from rag_service.db.session import create_engine, create_session_factory
from rag_service.infrastructures.providers.hf_embedding_provider import HuggingFaceEmbeddingProvider
from rag_service.infrastructures.providers.local_embedding_provider import LocalEmbeddingProvider
from rag_service.domain.qdrant_vector_storage import QdrantVectorStorage
from rag_service.infrastructures.providers.vector_storage_provider import NullVectorProvider, VectorProvider
from rag_service.application.retrieve_service import HttpLLMProvider, SearchService


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs from .env if variable is not already set."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _derive_async_db_url() -> str:
    db_url = os.getenv("RAG_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL or RAG_DATABASE_URL is not set")
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url
    if db_url.startswith("postgresql+psycopg2://"):
        return "postgresql+asyncpg://" + db_url[len("postgresql+psycopg2://") :]
    if db_url.startswith("postgresql+psycopg://"):
        return "postgresql+asyncpg://" + db_url[len("postgresql+psycopg://") :]
    if db_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + db_url[len("postgresql://") :]
    if db_url.startswith("postgres://"):
        return "postgresql+asyncpg://" + db_url[len("postgres://") :]
    raise RuntimeError(f"Unsupported database URL scheme: {db_url}")


def _to_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _build_vector_provider() -> VectorProvider:
    qdrant_url = os.getenv("QDRANT_URL")
    collection = os.getenv("COLLECTION_NAME") or os.getenv("QDRANT_COLLECTION")
    if not qdrant_url or not collection:
        print("[SMOKE] Qdrant is not configured; using NullVectorProvider")
        return NullVectorProvider()

    backend = (os.getenv("EMBEDDING_BACKEND") or "local").lower()
    if backend == "hf":
        model = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
        token = os.getenv("HF_TOKEN")
        if not token:
            raise RuntimeError("HF_TOKEN is required when EMBEDDING_BACKEND=hf")
        embedding = HuggingFaceEmbeddingProvider(model=model, token=token)
    else:
        model = os.getenv("LOCAL_EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
        embedding = LocalEmbeddingProvider(model=model)

    print(f"[SMOKE] Qdrant provider: url={qdrant_url} collection={collection} backend={backend} model={model}")
    return QdrantVectorStorage(
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


async def _run(query: str, top_k: int, doc_id: str | None) -> None:
    db_url = _derive_async_db_url()
    engine = create_engine(db_url)
    session_factory: async_sessionmaker[AsyncSession] = create_session_factory(engine)

    vector_provider = _build_vector_provider()
    llm_provider = HttpLLMProvider()
    service = SearchService(
        session_factory=session_factory,
        vector_provider=vector_provider,
        llm_provider=llm_provider,
        max_context_chars=int(os.getenv("MAX_CONTEXT_CHARS", "12000")),
    )

    doc_uuid: uuid.UUID | None = uuid.UUID(doc_id) if doc_id else None
    result = await service.search(query=query, top_k=top_k, doc_id=doc_uuid)

    print("\n[SMOKE] RESULT")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:20000])

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone retriever smoke test")
    parser.add_argument("query", help="User query text")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--doc-id", type=str, default=None)
    args = parser.parse_args()

    _load_env_file(Path(__file__).resolve().parents[1] / ".env")
    _load_env_file(Path(__file__).resolve().parents[2] / ".env")

    asyncio.run(_run(args.query, args.top_k, args.doc_id))


if __name__ == "__main__":
    main()
