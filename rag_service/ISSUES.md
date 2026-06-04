# RAG Service — Issues & Fixes

## 🔴 Баги (реальные ошибки в поведении)

| # | Описание | Файл | Строка | Статус |
|---|---|---|---|---|
| B1 | Двойной `status=ERROR` при падении — `update_document(ERROR)` вызывается и в `IngestionService`, и в `task.py` | `workers/ingestion_service.py`, `workers/task.py` | 142–148, 32–37 | ⬜ Открыт |
| B2 | `KeyError` перед guard-проверкой: `points[0].get("vector")["dense_vector"]` падает до `if not first_vector` | `infrastructures/repositories/qdrant_vector_storage.py` | 106–108 | ⬜ Открыт |
| B3 | `score_threshold` в `search()` не доходит до Qdrant — в `_build_prefetch` захардкожен `score_threshold=None` | `infrastructures/repositories/qdrant_vector_storage.py` | 217–231 | ⬜ Открыт |
| B4 | `total` в ответе неверный: `total = len(parent_key)` (из БД), а не `len(items)` (реально возвращённых) | `application/retrieve_service.py` | 258 | ⬜ Открыт |
| B5 | Все ошибки `stat()` при удалении становятся "file not found" — таймаут и 500 от MinIO дают 404 | `application/document_orchestrator.py` | 64–66 | ⬜ Открыт |

---

## 🟠 Архитектурные / поведенческие проблемы

| # | Описание | Файл | Строка | Статус |
|---|---|---|---|---|
| A1 | `_ensure_collection` вызывается при каждом upsert — лишний `collection_exists()` к Qdrant на каждый документ | `infrastructures/repositories/qdrant_vector_storage.py` | 111 | ⬜ Открыт |
| A2 | `source` в child chunks — временный путь `/tmp/xyz/doc.pdf`, который не существует после ingestion | `application/chunking_pipeline.py` | 58 | ⬜ Открыт |
| A3 | N+1 запросов к S3 в `get_list_document` — отдельный `stat()` на каждый документ последовательно | `application/document_orchestrator.py` | 83–86 | ⬜ Открыт |
| A4 | `doc_id` в Celery-задаче — тип `uuid.UUID` в сигнатуре, но реально приходит `str` через JSON-сериализацию | `workers/task.py` | 17 | ⬜ Открыт |
| A5 | Webhook-токен через `os.getenv` вместо `pydantic-settings` — нарушение архитектурного соглашения | `api/rag_routes.py` | 85 | ⬜ Открыт |
| A6 | Глобальные mutable переменные без thread-safety — race condition при параллельном старте воркеров | `infrastructure.py` | 72–84, 154–167 | ⬜ Открыт |
| A7 | Ключ дедупликации в `group_hits_by_parent` — только `parent_id`, а не `(doc_id, parent_id)` как указано в комментарии | `application/retrieve_service.py` | 217 | ⬜ Открыт |

---

## 🟡 Типы / стиль / неточности

| # | Описание | Файл | Строка | Статус |
|---|---|---|---|---|
| T1 | `raise e` вместо `raise` — теряется оригинальный traceback | `workers/ingestion_service.py` | 149 | ⬜ Открыт |
| T2 | Deprecated typing imports: `List`, `Dict`, `Optional` вместо `list`, `dict` из built-ins | `workers/ingestion_service.py` | 8–9 | ⬜ Открыт |
| T3 | Неиспользуемый `import asyncio` | `workers/ingestion_service.py` | 3 | ⬜ Открыт |
| T4 | Неиспользуемый `import re` | `application/document_orchestrator.py` | 4 | ⬜ Открыт |
| T5 | Дублирующиеся импорты `uuid` и `Any` — объявлены дважды в одном файле | `domain/chunking/document_parser.py` | 122–123 | ⬜ Открыт |
| T6 | Misleading переменная `existing_by_name` — проверка идёт по `doc_id`, а не по имени | `application/document_service.py` | 125 | ⬜ Открыт |
| T7 | Аннотация `status: str` вместо `status: DocumentStatus` в `update_document_hash_atomically` | `application/document_service.py` | 57 | ⬜ Открыт |
| T8 | `requested_parent_ids` — передаются строки, `get_parent_chunks` ожидает `list[uuid.UUID]` | `application/retrieve_service.py` | 105, 164 | ⬜ Открыт |
| T9 | `BatchDeleteDocumentsResponse.failed` — роут собирает `list[dict]`, схема ожидает `list[BatchDeleteErrorItem]` | `api/rag_routes.py`, `api/schemas.py` | 173, 125 | ⬜ Открыт |
| T10 | Бесполезный `try/except/raise` без обработки в `generate_link_upload_file` | `api/rag_routes.py` | 74–76 | ⬜ Открыт |
| T11 | `GET /documents` использует write-сервис `DataBaseDocumentService` для read-only запроса | `api/rag_routes.py` | 125–127 | ⬜ Открыт |
| T12 | `GET /documents` без `response_model` — схема `DocumentSummaryResponse` есть, но не подключена | `api/rag_routes.py` | 124 | ⬜ Открыт |
| T13 | `PlaceholderActionResponse.detail` — обязательное поле без дефолта, раскомментированные роуты сломаются | `api/schemas.py` | 128–131 | ⬜ Открыт |

---

## 🗑️ Мёртвый код

| # | Описание | Файл | Статус |
|---|---|---|---|
| D1 | ~200 строк закомментированных роутов (включая дубль `DELETE /documents/{doc_id}`) | `api/rag_routes.py:95–301` | ⬜ Открыт |
| D2 | ~70 строк закомментированного примера Celery-таска | `workers/task.py:41–112` | ⬜ Открыт |
| D3 | `_compute_hash` статический метод — хеш считается в `IngestionService`, не здесь | `application/document_orchestrator.py:128–129` | ⬜ Открыт |
| D4 | `dispatch_reindexing()` пустой stub | `application/task_dispatcher_service.py:26–30` | ⬜ Открыт |
| D5 | `broker_client` параметр конструктора и `self.broker` — нигде не используются | `application/task_dispatcher_service.py:11–12` | ⬜ Открыт |
| D6 | `update_metadata_document()` пустой stub (`pass`) | `application/document_service.py:198–199` | ⬜ Открыт |
| D7 | `set_status()` дублирует `update_document()` и нигде не вызывается | `application/document_service.py:160–169` | ⬜ Открыт |
| D8 | `sparse_bm25_provider.py` — BM25 реализован нативно в Qdrant | `infrastructures/providers/sparse_bm25_provider.py` | ⬜ Открыт |
| D9 | `hf_embedding_provider.py` — используется локальный провайдер | `infrastructures/providers/hf_embedding_provider.py` | ⬜ Открыт |
| D10 | `document_repository_provider.py` — неясный factory, нигде не используется | `infrastructures/providers/document_repository_provider.py` | ⬜ Открыт |
| D11 | `statick_test.py` — неясное содержимое, не подключён ни к одному runner | `tests/statick_test.py` | ⬜ Открыт |