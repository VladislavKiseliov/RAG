# RAG Service — Issues & Fixes

## 🔴 Баги

| # | Описание | Файл | Строка |
|---|---|---|---|
| B3 | `score_threshold` в `search()` не доходит до Qdrant — в `query_points` не передаётся | `infrastructures/repositories/qdrant_vector_storage.py` | ~190 |

---

## 🟠 Архитектурные / поведенческие проблемы

| # | Описание | Файл | Строка |
|---|---|---|---|
| A1 | `_ensure_collection` вызывается при каждом upsert — лишний `collection_exists()` к Qdrant на каждый документ | `infrastructures/repositories/qdrant_vector_storage.py` | ~300 |
| A9 | **OOM при инжекте:** `bm25_sparse_vector` строит инвертированный индекс в RAM → Qdrant крашится и обрывает соединение. Фикс: добавить `index=models.SparseIndexParams(on_disk=True)` в `SparseVectorParams` при `create_collection`. **Важно:** требует пересоздания коллекции и переиндексации всех документов. | `infrastructures/repositories/qdrant_vector_storage.py` | ~329 |
| A2 | `source` в child chunks — временный путь `/tmp/xyz/doc.pdf`, который не существует после ingestion | `application/chunking_pipeline.py` | 58 |
| A5 | Webhook-токен через `os.getenv` вместо `pydantic-settings` — нарушение архитектурного соглашения | `api/rag_routes.py` | ~85 |
| A6 | Глобальный синглтон `v_indexing_service` без thread-safety — race condition при параллельном старте воркеров | `infrastructure.py` | ~71 |
| A7 | Ключ дедупликации в `group_hits_by_parent` — только `parent_id`, а не `(doc_id, parent_id)` | `application/retrieve_service.py` | ~217 |
| A8 | `DocumentStatus` определён в `api/schemas.py` — домен и воркеры импортируют из API-слоя | `api/schemas.py` | 8–23 |

---

## 🟡 Типы / стиль / неточности

| # | Описание | Файл | Строка |
|---|---|---|---|
| T1 | `raise e` вместо `raise` — теряется оригинальный traceback | `workers/ingestion_service.py` | ~150 |
| T2 | Deprecated: `List`, `Dict` вместо `list`, `dict` из built-ins | `workers/ingestion_service.py` | 9 |
| T5 | Дублирующиеся импорты `uuid` и `Any` | `domain/chunking/document_parser.py` | 122–123 |
| T6 | Misleading переменная `existing_by_name` — проверка идёт по `doc_id`, а не по имени | `application/document_service.py` | ~125 |
| T7 | Аннотация `status: str` вместо `status: DocumentStatus` | `application/document_service.py` | ~57 |
| T8 | `requested_parent_ids` — передаются строки, `get_parent_chunks` ожидает `list[uuid.UUID]` | `application/retrieve_service.py` | 105, 164 |
| T9 | `BatchDeleteDocumentsResponse.failed` — роут собирает `list[dict]`, схема ожидает `list[BatchDeleteErrorItem]` | `api/rag_routes.py`, `api/schemas.py` | — |
| T10 | Бесполезный `try/except/raise` в `generate_link_upload_file` | `api/rag_routes.py` | ~74 |
| T11 | `GET /documents` использует write-сервис для read-only запроса | `api/rag_routes.py` | ~125 |
| T12 | `GET /documents` без `response_model` — схема `DocumentSummaryResponse` есть, но не подключена | `api/rag_routes.py` | ~124 |
| T13 | `PlaceholderActionResponse.detail` — обязательное поле без дефолта | `api/schemas.py` | ~128 |

---

## 🗑️ Мёртвый код

| # | Описание | Файл |
|---|---|---|
| D1 | ~200 строк закомментированных роутов | `api/rag_routes.py` |
| D4 | `dispatch_reindexing()` пустой stub | `application/task_dispatcher_service.py` |
| D5 | `broker_client` и `self.broker` — нигде не используются | `application/task_dispatcher_service.py` |
| D6 | `update_metadata_document()` пустой stub (`pass`) | `application/document_service.py` |
| D7 | `set_status()` дублирует `update_document()` и нигде не вызывается | `application/document_service.py` |