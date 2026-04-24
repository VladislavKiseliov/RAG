"""PDF chunking engine with optional ingestion into Postgres and Qdrant."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import pymupdf4llm
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Allow running this file directly: python rag_service/rag_core_test/ChinkingEngine.py
if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from rag_service.models import DocumentStatus
from rag_service.infrastructures.providers.vector_storage_provider import VectorProvider
from rag_service.infrastructures.repositories.document_repository import DocumentRepository
from rag_service.application.document_service import DocumentService


class DocumentProcessor:
    """Extracts structured parent/child chunks from PDF and can persist them."""

    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 40) -> None:
        """Configure child chunking parameters in characters."""
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.seen_hashes: set[str] = set()

    @staticmethod
    def file_hash(content: bytes) -> str:
        """Compute SHA-256 hash for deduplication."""
        return hashlib.sha256(content).hexdigest()

    def get_content_hash(self, text: str) -> str:
        """Compute normalized hash to deduplicate near-identical parent text."""
        normalized = re.sub(r"\s+", "", text)
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def is_table_of_contents(self, text: str) -> bool:
        """Heuristic check to skip table-of-contents pages."""
        toc_keywords = ["СОДЕРЖАНИЕ", "ОГЛАВЛЕНИЕ", "TABLE OF CONTENTS", "СПИСОК РАЗДЕЛОВ"]
        if any(kw in text.upper()[:200] for kw in toc_keywords):
            return True
        lines = text.split("\n")
        toc_patterns = [line for line in lines if re.search(r"\.{3,}\s*\d+", line)]
        return len(toc_patterns) > 2


    def split_by_physical_pages(self, text: str) -> list[dict[str, str]]:
        """Split markdown section text by detected page number separators."""
        pattern = r"\n\s*(\d+)\s*\n"
        parts = re.split(pattern, text)
        pages: list[dict[str, str]] = []

        if parts and parts[0].strip():
            pages.append({"num": "N/A", "content": parts[0].strip()})

        for i in range(1, len(parts), 2):
            num = parts[i]
            content = parts[i + 1].strip() if (i + 1) < len(parts) else ""
            if content:
                pages.append({"num": num, "content": content})

        return pages

    def split_to_children(self, text: str) -> list[str]:
        """Split parent text into child chunks for vectorization."""
        point_pattern = r"\n(?=\d+\.\d+(?:\.\d+)*\s)"
        if re.search(r"\d+\.\d+", text):
            items = re.split(point_pattern, text)
            results = [item.strip() for item in items if len(item.strip()) > 20]
            if len(results) > 1:
                return results

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return [chunk.strip() for chunk in splitter.split_text(text) if len(chunk.strip()) > 20]

    def process_document(self, file_path: str) -> list[dict[str, Any]]:
        """Return parent chunks with child chunks extracted from a PDF file."""
        if not os.path.exists(file_path):
            return []

        self.seen_hashes.clear()
        md_text = pymupdf4llm.to_markdown(file_path)

        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[("#", "H1"), ("##", "H2"), ("###", "H3")],
            strip_headers=False,
        )
        structural_sections = header_splitter.split_text(md_text)

        all_data: list[dict[str, Any]] = []

        for section in structural_sections:
            pages = self.split_by_physical_pages(section.page_content)

            for page in pages:
                page_text = self.clean_content(page["content"])

                if self.is_table_of_contents(page_text) or len(page_text) < 50:
                    continue

                content_hash = self.get_content_hash(page_text)
                if content_hash in self.seen_hashes:
                    continue
                self.seen_hashes.add(content_hash)

                parent_id = str(uuid.uuid4())[:8]
                parent_obj: dict[str, Any] = {
                    "id": parent_id,
                    "page_num": page["num"],
                    "headers": section.metadata,
                    "text": page_text,
                    "children": [],
                }

                child_texts = self.split_to_children(page_text)
                for child_text in child_texts:
                    parent_obj["children"].append(
                        {
                            "parent_id": parent_id,
                            "text": child_text,
                            "metadata": section.metadata,
                        }
                    )

                all_data.append(parent_obj)

        return all_data

    @staticmethod
    def _build_rows_and_points(structured_data: list[dict[str, Any]], source: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Convert parsed structure into Postgres rows and Qdrant points."""
        parent_rows: list[dict[str, Any]] = []
        points: list[dict[str, Any]] = []

        for parent in structured_data:
            parent_id = str(parent["id"])
            page_num = str(parent.get("page_num") or "N/A")
            headers = parent.get("headers") or {}
            text = str(parent.get("text") or "")

            if not text:
                continue

            parent_rows.append(
                {
                    "parent_id": parent_id,
                    "text": text,
                    "page_num": page_num,
                    "headers": headers,
                }
            )

            children = parent.get("children") or []
            for idx, child in enumerate(children):
                child_text = str(child.get("text") or "").strip()
                if not child_text:
                    continue
                points.append(
                    {
                        "id": f"{parent_id}:{idx}",
                        "text": child_text,
                        "payload": {
                            "text": child_text,
                            "parent_id": parent_id,
                            "page_num": page_num,
                            "headers": headers,
                            "source": source,
                        },
                    }
                )

        return parent_rows, points

    async def ingest_pdf(
        self,
        *,
        file_path: str,
        session_factory: async_sessionmaker[AsyncSession],
        vector_provider: VectorProvider,
        meta: dict[str, Any] | None = None,
        doc_id: uuid.UUID | None = None,
        vector_timeout_seconds: float = 60.0,
    ) -> dict[str, Any]:
        """Ingest one PDF: validate -> dedup -> Postgres -> Qdrant -> completed."""
        if not os.path.exists(file_path):
            raise ValueError("File path does not exist")
        if not os.path.isfile(file_path):
            raise ValueError("Path is not a file")
        if not file_path.lower().endswith(".pdf"):
            raise ValueError("Only PDF is supported in this flow")

        with open(file_path, "rb") as fp:
            content = fp.read()
        if not content:
            raise ValueError("Empty file")

        file_hash = self.file_hash(content)
        filename = os.path.basename(file_path)

        structured_data = self.process_document(file_path)
        if not structured_data:
            raise ValueError("No structured chunks produced")

        parent_rows, points = self._build_rows_and_points(structured_data, source=filename)
        if not parent_rows:
            raise ValueError("No parent chunks produced")
        if not points:
            raise ValueError("No child chunks produced")

        async with session_factory() as session:
            repo = DocumentRepository(session)
            service = DocumentService(session)

            existing = await repo.get_document_by_hash(file_hash)
            if existing is not None:
                if existing.status == DocumentStatus.completed:
                    return {"doc_id": str(existing.id), "status": existing.status.value, "chunk_count": existing.chunk_count}
                if existing.status == DocumentStatus.processing:
                    return {"doc_id": str(existing.id), "status": existing.status.value, "chunk_count": existing.chunk_count}

            try:
                if existing is not None and existing.status == DocumentStatus.error:
                    await repo.delete_document(existing.id)
                    await session.flush()

                created_id = await service.create_doc(filename, file_hash, meta, doc_id=doc_id)
                await service.add_parent_chunks(created_id, parent_rows)

                for point in points:
                    point["payload"]["doc_id"] = str(created_id)

                await asyncio.wait_for(
                    vector_provider.upsert_with_payload(created_id, points),
                    timeout=vector_timeout_seconds,
                )

                await service.set_status(created_id, DocumentStatus.completed, chunk_count=len(points))
                await session.commit()
                return {"doc_id": str(created_id), "status": DocumentStatus.completed.value, "chunk_count": len(points)}
            except Exception:
                await session.rollback()
                raise


if __name__ == "__main__":
    import sys

    from rag_service.db.session import create_engine, create_session_factory
    from rag_service.infrastructures.providers.hf_embedding_provider import HuggingFaceEmbeddingProvider
    from rag_service.infrastructures.providers.local_embedding_provider import LocalEmbeddingProvider
    from rag_service.domain.qdrant_vector_storage import QdrantVectorStorage

    def _load_env_file(path: Path) -> None:
        """Load simple KEY=VALUE pairs from .env into os.environ if missing."""
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

    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "132.pdf"
    processor = DocumentProcessor()

    # Load project env files for standalone script runs.
    _load_env_file(Path(__file__).resolve().parents[1] / ".env")
    _load_env_file(Path(__file__).resolve().parents[2] / ".env")

    print(f"[TEST] PDF path: {pdf_path}")
    structured_data = processor.process_document(pdf_path)
    print(f"[TEST] Parents extracted: {len(structured_data)}")
    print(f"[TEST] Children extracted: {sum(len(parent.get('children', [])) for parent in structured_data)}")

    for parent in structured_data[:3]:
        print(f"[PARENT] id={parent['id']} page={parent['page_num']} children={len(parent['children'])}")
        print(f"[PARENT] headers={parent['headers']}")
        print("-" * 40)

    db_url = os.getenv("RAG_DATABASE_URL") or os.getenv("DATABASE_URL") or "postgresql+psycopg2://myuser:mypassword@localhost:5432/myapp_db"
    qdrant_url = os.getenv("QDRANT_URL") or "http://localhost:6333"
    collection = os.getenv("COLLECTION_NAME") or os.getenv("QDRANT_COLLECTION") or "rag_documents"
    hf_token = os.getenv("HF_TOKEN")
    embedding_backend = (os.getenv("EMBEDDING_BACKEND") or "local").lower()
    if embedding_backend == "hf":
        embedding_model = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
    else:
        embedding_model = os.getenv("LOCAL_EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    vector_timeout_seconds = float(os.getenv("VECTOR_TIMEOUT_SECONDS", "300"))

    if not db_url:
        print("[TEST] Skip ingest: DATABASE_URL/RAG_DATABASE_URL is not set")
        raise SystemExit(0)

    if db_url.startswith("postgresql+psycopg2://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgresql+psycopg2://") :]
    elif db_url.startswith("postgresql+psycopg://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgresql+psycopg://") :]
    elif db_url.startswith("postgresql://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgresql://") :]
    elif db_url.startswith("postgres://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgres://") :]

    if not db_url.startswith("postgresql+asyncpg://"):
        print("[TEST] Skip ingest: unsupported DB URL scheme")
        raise SystemExit(0)

    session_factory = create_session_factory(create_engine(db_url))

    if embedding_backend == "hf":
        if not hf_token:
            raise RuntimeError("HF_TOKEN is required when EMBEDDING_BACKEND=hf")
        embedding = HuggingFaceEmbeddingProvider(model=embedding_model, token=hf_token)
    else:
        embedding = LocalEmbeddingProvider(model=embedding_model)

    vector_provider: VectorProvider = QdrantVectorStorage(
        url=qdrant_url,
        collection=collection,
        embedding_provider=embedding,
    )
    print(
        f"[TEST] Qdrant provider enabled: url={qdrant_url} collection={collection} "
        f"backend={embedding_backend} model={embedding_model}"
    )

    result = asyncio.run(
        processor.ingest_pdf(
            file_path=pdf_path,
            session_factory=session_factory,
            vector_provider=vector_provider,
            meta={"source": "__main__ test"},
            vector_timeout_seconds=vector_timeout_seconds,
        )
    )
    print(f"[TEST] Ingest result: {result}")
