from typing import Any, Dict, List
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models


class QdrantIngestClient:
    """Minimal Qdrant client wrapper for ingestion."""

    def __init__(self, url: str, collection: str) -> None:
        self.client = QdrantClient(url=url)
        self.collection = collection

    def _ensure_collection(self, vector_size: int) -> None:
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection for c in collections)
        if exists:
            return

        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )

    def upsert(self, vectors: List[List[float]], payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not vectors:
            raise ValueError("Vectors list is empty")
        if len(vectors) != len(payloads):
            raise ValueError("Vectors and payloads length mismatch")

        self._ensure_collection(len(vectors[0]))

        points = [
            models.PointStruct(
                id=uuid4().hex,
                vector=vector,
                payload=payload,
            )
            for vector, payload in zip(vectors, payloads)
        ]

        result = self.client.upsert(collection_name=self.collection, points=points)
        return {"status": result.status, "count": len(points)}
