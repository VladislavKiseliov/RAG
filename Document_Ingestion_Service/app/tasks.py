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
        raise RuntimeError("Embeddings models initialization failed")

    # 1. Вызываем процессор для получения структурированных данных (Parent-Child)
    processor = DocumentProcessor()
    structured_chunks = processor.process_document(file_path)

    if not structured_chunks:
        raise RuntimeError("Document ingestion returned empty result")

    # 2. Распределяем данные: готовим плоские списки для векторной базы и SQL
    payloads = []
    texts_for_embedding = []

    for parent in structured_chunks:
        p_id = parent["id"]
        p_text = parent["text"]
        p_page = parent["page_num"]
        p_headers = parent["headers"]

        for child in parent["children"]:
            chunk_text = child["text"]
            texts_for_embedding.append(chunk_text)

            # Формируем payload, распределяя данные:
            # Ребенок идет в векторный поиск, Родитель (p_text) сохраняется для SQL контекста
            payloads.append({
                "id": str(uuid.uuid4()),
                "text": chunk_text,  # Чанк для поиска
                "parent_id": p_id,  # ID для связи в SQL
                "parent_text": p_text,  # Полный текст страницы для выдачи
                "metadata": {
                    **p_headers,
                    "page_label": p_page,
                    "source": os.path.basename(file_path),
                    "collection": collection
                }
            })

    # 3. Генерация векторов для всех распределенных чанков
    vectors = embeddings.embed_documents(texts_for_embedding)

    # 4. Наложение дополнительных метаданных, если они переданы
    if metadata:
        for payload in payloads:
            payload_meta = payload.get("metadata") or {}
            payload_meta.update(metadata)
            payload["metadata"] = payload_meta

    # 5. Загрузка в базу
    client = QdrantIngestClient(QDRANT_URL, collection)
    upsert_info = client.upsert(vectors, payloads)

    # Возвращаем финальный результат
    # return {
    #     "collection": collection,
    #     "chunks": len(vectors),
    #     "upsert": upsert_info,
    # }


















    if embeddings is None:
        raise RuntimeError("Embeddings models initialization failed")

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
