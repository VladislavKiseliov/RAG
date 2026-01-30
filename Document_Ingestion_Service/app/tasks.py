from celery import Celery

from .config import QDRANT_URL, REDIS_URL
from .document_processing import ingest_document, initialization_embeddings_model
from .services.qdrant_client import QdrantIngestClient


celery_app = Celery(
    "document_ingestion_service",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

embeddings = initialization_embeddings_model()


@celery_app.task(name="ingest_pdf_task")
def ingest_pdf_task(file_path: str, collection: str, metadata: dict | None = None) -> dict:
    if embeddings is None:
        raise RuntimeError("Embeddings model initialization failed")

    result = ingest_document(file_path, embeddings, collection)
    if not result:
        raise RuntimeError("Document ingestion returned empty result")

    payloads = result["payload"]
    vectors = result["vector"]

    if metadata:
        for payload in payloads:
            payload_meta = payload.get("metadata") or {}
            payload_meta.update(metadata)
            payload["metadata"] = payload_meta

    client = QdrantIngestClient(QDRANT_URL, collection)
    upsert_info = client.upsert(vectors, payloads)

    return {
        "collection": collection,
        "chunks": len(vectors),
        "upsert": upsert_info,
    }
