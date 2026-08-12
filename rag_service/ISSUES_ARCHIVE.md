# RAG Service — Issues & Fixes: архив закрытого

Все пункты ниже исправлены и подтверждены (тестами и/или живым прогоном). Вынесено сюда из
`ISSUES.md`, чтобы там оставались только открытые B/A/D-пункты. Хронологический порядок сохранён.

---

## ✅ Исправлено (сессия Docling-рефакторинга)

| # | Было | Как исправлено |
|---|---|---|
| A2 | `source` в child chunks — временный путь во `TemporaryDirectory()` | Временные файлы убраны полностью — конвертация PDF идёт через bytes/`DocumentStream` от S3 до Docling, temp-директорий в пайплайне больше нет |
| T1 | `raise e` вместо `raise` — терялся traceback | `application/ingestion_service.py` переписан с явной политикой исключений (retry/no-retry по типу), голого `raise e` не осталось |
| T5 | Дублирующиеся импорты `uuid`/`Any` | `document_parser.py` → `chunk_builder.py`, файл реструктурирован (датаклассы `ParentChunk`/`ChildChunk`), импорты собраны в одном месте |

## ✅ Исправлено (2026-07-17)

| # | Было | Как исправлено |
|---|---|---|
| B4 | Ретрай Celery не идемпотентен: `_store_structural_data` при повторной попытке заново вставляла те же `document_chapters`/`document_tables`/parent chunks → `UniqueViolationError` на `uq_document_chapters_doc_chapter_number`, которая сама классифицировалась как "transient" и ретраилась бесконечно до исчерпания `max_retries` | `DocumentRepository.delete_structural_data()` + `DataBaseDocumentService.reset_structural_data()`, вызывается в начале `IngestionService._store_structural_data()` — ретрай теперь стартует с чистого состояния |

## ✅ Исправлено (2026-07-20)

| # | Было | Как исправлено |
|---|---|---|
| B5 | Ретрай-политика ловила `DBAPIError` целиком как "транзиентную инфраструктуру" — базовый класс и для `IntegrityError`/`ProgrammingError`/`DataError`, не только connection/timeout. Реальный constraint-баг ретраился бы молча до `max_retries` вместо немедленного ERROR | `ingestion_service.py` — из except-кортежа убран `DBAPIError`, оставлен только `OperationalError` (специфично про соединение/операционные сбои). Всё остальное из `DBAPIError` теперь падает в общий `except Exception` → `doc.fail()` + статус ERROR сразу |
| B6 | Webhook от MinIO обрабатывал `event.records` без per-record try/except — упавшая запись рвала весь ответ non-200, MinIO ретраил весь вебхук, уже задиспатченные записи продиспатчились бы повторно | `rag_routes.py::handle_webhook` — per-record try/except, 200 всегда (кроме сбоя авторизации), список `failed` в ответе при частичном провале. Плюс идемпотентность в `TaskDispatcherService.dispatch_ingestion` — пропускает диспатч, если `doc.status != PENDING` |

## ✅ Исправлено (2026-07-21)

| # | Было | Как исправлено |
|---|---|---|
| B7 | `delete_by_field` падал, если целевая Qdrant-коллекция ещё не существует (первый когда-либо апсерт в неё, например самая первая заметка пользователя) — Celery ретраил 3 раза и сдавался, сущность навсегда оставалась неиндексированной | `infrastructures/repositories/qdrant_vector_storage.py` — отсутствующую коллекцию теперь просто пропускают (нечего удалять), а не бросают исключение. Найдено по ходу работы над Заметками, не отдельная задача |

## ✅ Исправлено (2026-07-22)

| # | Было | Как исправлено |
|---|---|---|
| D4 | `dispatch_reindexing()` пустой stub — кнопка «↻ Переиндексировать» в админке ничего не делала, роута в rag_service не было вообще | Переиспользует ту же `ingest_document_task`, что и первичная загрузка (`process_document` уже идемпотентен по Postgres). Добавлен `POST /documents/{doc_id}/reindex` в `rag_routes.py`. Попутно закрыт скрытый баг: `_run_pipeline` вставлял новые чанки под новыми `point_id`, не трогая старые — реиндекс плодил бы в Qdrant дубликаты. Перед индексацией теперь `vector_storage.delete_by_field("doc_id", ...)` сносит старые векторы документа (`ingestion_service.py`), `VectorDeleteError` добавлен в список транзиентных ошибок, которые ретраит Celery |
| T14 | UTF-8 BOM в начале файла (`ef bb bf`) | BOM снят напрямую (`open(...,"rb")`, срез первых 3 байт) — `git diff` подтверждает единственное реальное изменение (первая строка), `py_compile` чисто |
| T15 | BOM + CRLF-концовки строк | BOM снят, `\r\n` → `\n`; `git diff` показал, что CRLF был лишь локальным артефактом Windows-чекаута (`core.autocrlf`) — в самом блобе строки уже хранились как LF, реально изменилась только первая строка |
| T16 | Опечатки в именах файлов | `git mv local_embedding_reposittory.py → local_embedding_repository.py`, `git mv ChinkingEngine.py → ChunkingEngine.py` (история сохранена через `git mv`). Импорты поправлены в `container.py` и внутри самого файла (`if __name__ == "__main__"` блок). Заодно снят найденный по ходу BOM в `ChunkingEngine.py` (не был в исходном списке ревью) |

## ✅ Исправлено (2026-07-24)

| # | Было | Как исправлено |
|---|---|---|
| B8 | (backend, не rag_service) `Chats.summary_link` в модели и в корневой миграции типизирован как `UUID(as_uuid=True)`, а `ConversationService` везде трактует его как integer — id последнего сообщения в батче, курсор для `get_messages_after`. Каждый раз, когда чат переваливает `SUMMARY_THRESHOLD` и `update_summary()` пытается сохранить `chat.summary_link = <int>`, запись падала с ошибкой типа | `backend/models/database_models.py:115` → `Integer`; та же правка в `migrations/users/versions/8506a89ad7d9_..._.py:67` (pre-release база, миграция поправлена на месте, не поверх). `ALTER TABLE users_shema.chats ALTER COLUMN summary_link TYPE INTEGER USING NULL` выполнен на dev-БД (`myapp_db`) — у всех 25 чатов значение было `NULL`, данных не потеряно. `rag_backend` перезапущен, поднялся чисто |
| B9 | `ChapterSplitter` путал нумерованные шаги внутри примеров («Пример N» → «1. Исходные данные.») с настоящими главами документа — коллизия номеров роняла `bulk_insert_chapters` на `UniqueViolationError`, плюс тихая порча данных (контент примера утекал не в ту главу) | `docling_segmenter.py::ChapterSplitter.split()` — `seen_numbers: set[str]`, номер, который уже встречался, дописывается в текущую главу вместо открытия новой (коммит `073a260`) |

## ✅ Исправлено (2026-07-28)

| # | Было | Как исправлено |
|---|---|---|
| B3 | `score_threshold` в `search()` не доходил до Qdrant — `query_points()` вызывался без этого kwarg (в `batch_search()` передавался корректно, асимметрия между методами). Реальный эффект: `RetrieveService.search()` вызывающие код передавали `score_threshold`, ожидая отсечение нерелевантных чанков, но фильтрация молча не работала — приходили все top_k результатов независимо от скора | `infrastructures/repositories/qdrant_vector_storage.py::search()` — `score_threshold=score_threshold` добавлен в вызов `query_points()`. Тест: `tests/test_qdrant_vector_storage_search.py` |
| B10 | `DocumentOrchestrator.delete_document` чистил только оригинальный файл (`document.s3key`) + Qdrant + Postgres. Производные S3-артефакты инжеста (`{doc_id}/full.md`, `chapters/*.md`, `tables/*.csv\|html`, `meta/*.md`) не удалялись никогда — подтверждено живьём (`mc ls` после `DELETE /documents/{id}` всё ещё показывал эти файлы). Утечка объектов в MinIO с каждым удалённым документом | Оригинальный файл и все производные артефакты лежат под одним префиксом `{doc_id}/` (см. `IngestionDocument.create_new`, `IngestionService._store_docling_artifacts`) — `delete_document` теперь листит `s3_storage.list(prefix=str(doc_id))` и удаляет всё найденное. Тест: `tests/test_document_orchestrator_delete.py::test_delete_document_removes_derivative_ingestion_artifacts` |
| A12 | Пайплайн инжеста сам себе слал вебхуки — записи собственных артефактов (`full.md`, `chapters/*`, `tables/*`, `meta/*`) триггерили `handle_webhook` → `DocumentByStorageKeyNotFound` → ERROR-лог, до сотни лишних записей на документ | `TaskDispatcherService._is_ingestion_artifact()` — проверка по суффиксам пути перед обращением к БД, тихий `return`. Тест: `tests/test_task_dispatcher_service.py` |

## ✅ Исправлено (2026-07-31)

| # | Было | Как исправлено |
|---|---|---|
| A1 | `_ensure_collection` вызывался при каждом upsert — лишний `collection_exists()` к Qdrant на каждый документ, даже после того как коллекция уже подтверждена | `QdrantVectorStorage` — флаг `self._collection_ready`, double-checked locking: после первого успешного создания/подтверждения коллекции все следующие вызовы возвращаются сразу, без похода в Qdrant и без lock |
| A5 | Webhook-токен читался через `os.getenv("MINIO_NOTIFY_WEBHOOK_AUTH_TOKEN_1")` вместо `pydantic-settings` — нарушение архитектурного соглашения | `RagSettings.minio_notify_webhook_auth_token_1` (`settings.py`), `rag_routes.py::handle_webhook` использует `settings.minio_notify_webhook_auth_token_1`; неиспользуемый `import os` убран |
| A6 | Глобальный синглтон `v_indexing_service` без thread-safety — `if v_indexing_service is None` без lock, race condition при параллельном старте воркеров | `container.py::get_v_indexing_service` — `threading.Lock` + double-checked locking |
| A7 | Докстринг/тайп-хинт `batch_search()` заявляли ключ дедупликации `(doc_id, parent_id)`, а по факту использовался голый `parent_id` — аннотация врала. Функционально не баг: `parent_id` — глобально уникальный PK `parent_chunks` (не составной с `doc_id`), коллизий между документами быть не может | `application/retrieve_service.py` | 191, 214–217 — докстринг и `seen: dict[str, dict]` приведены в соответствие с реальным поведением, ключ не менялся |
| A8 | `DocumentStatus` был определён в `api/schemas.py` — `domain/document.py`, `models/models.py`, `application/task_dispatcher_service.py` импортировали доменное понятие из API-слоя, зависимость в обратную сторону от DDD | `DocumentStatus` перенесён в `domain/document.py` (его естественный владелец); `api/schemas.py` реэкспортирует (`from rag_service.domain.document import DocumentStatus`) — внешние импорты не сломаны; `models/models.py` и `task_dispatcher_service.py` переключены на прямой импорт из `domain.document` |

## ✅ Исправлено (2026-07-31, T-серия)

| # | Было | Как исправлено |
|---|---|---|
| T2 | Deprecated: `List`, `Dict` вместо `list`, `dict` из built-ins | `application/ingestion_service.py` — файл уже использует `from __future__ import annotations`, все `List[...]`/`Dict` заменены на `list[...]`/`dict`, `from typing import List, Dict` убран |
| T6 | Misleading переменная `existing_by_name` — проверка идёт по `doc_id`, а не по имени | `application/document_service.py::create_doc` — переименована в `existing_by_id` |
| T7 | Аннотация `status: str` вместо `status: DocumentStatus` | `application/document_service.py::update_document_hash_atomically` — параметр типизирован `DocumentStatus`, внутри вызывается `status.value` при передаче в repo-слой (там `status: str` остаётся верным — граница с БД). Метод не имел внешних вызывающих кроме repo-слоя напрямую в тестах — смена типа безопасна |

## ✅ Исправлено (2026-07-31, T-серия продолжение)

| # | Было | Как исправлено |
|---|---|---|
| T8 | `requested_parent_ids` передавались строками, `get_parent_chunks`/`get_parents_by_ids` типизированы `list[uuid.UUID]` (работало только за счёт bind-процессора SQLAlchemy для UUID-колонки) | `application/retrieve_service.py::search`/`batch_search` — `requested_parent_ids = [uuid.UUID(key) for key in ...]`, тип совпадает с уже объявленной сигнатурой репозитория/сервиса |
| T9 | `BatchDeleteDocumentsResponse.failed` — роут собирал `list[dict]`, схема ожидает `list[BatchDeleteErrorItem]` (рантайм не ломался — pydantic коэрсил dict в модель при конструировании) | `api/rag_routes.py::batch_delete_documents` — `failed: list[BatchDeleteErrorItem]`, оба `.append(...)` строят реальные модели вместо dict |

## ✅ Исправлено (2026-07-31, T-серия завершение)

| # | Было | Как исправлено |
|---|---|---|
| T11 | `GET /documents` использовал write-сервис (`DocServiceDep`) вместо read-only `DocQueryServiceDep` | `api/rag_routes.py::list_documents` переключён на `DocQueryServiceDep` (`DocumentQueryService.list_documents` — идентичная сигнатура); неиспользуемый импорт `DocServiceDep` убран |
| T12 | `GET /documents` без `response_model` — схема `DocumentSummaryResponse` была неполной (не покрывала `s3key`/`size`/`has_summary`, которые роут реально отдавал и которые читает админ-панель фронта, `useAdmin.js:22,24`) | `DocumentSummaryResponse` дополнена полями `s3key`/`size`/`has_summary`, роут навешивает `response_model=list[DocumentSummaryResponse]` и строит модели явно вместо сырых dict — сначала расширил схему под реальный контракт, чтобы не отфильтровать поля, которые ест фронт |
| T13 | `PlaceholderActionResponse.detail` — обязательное поле без дефолта (используется только внутри закомментированных роутов D1) — раскомментировать было бы нельзя без `ValidationError` | `detail: str \| None = None` |

Всё найденное внешним код-ревью 2026-07-21 (лично перепроверено `grep`/прямым чтением файлов) закрыто 2026-07-22: rag_service-часть — T14–T16 (см. таблицу «Исправлено (2026-07-22)» выше); часть по другим сервисам, у которых нет своего ISSUES.md — `llm_service`: `retrieval_service.py` теперь держит один переиспользуемый `httpx.AsyncClient` вместо нового на каждый запрос (закрывается в `main.py::lifespan`), задвоенный `MLQueryRouter` в `query_service.py` удалён (мёртвый код), опечатка `row_query` → `raw_query`; `backend`: `auth_handler.decode_token` докстринг/тайп-хинт приведены в соответствие с реальным поведением (возвращает `dict`, кидает исключения, никогда не возвращает `None`), `ConversationService.update_summary` теперь сериализуется per-chat `asyncio.Lock`, чтобы два параллельных пересечения `SUMMARY_THRESHOLD` не гонялись за перезаписью `chat.summary`. Плюс `.idea/` untracked из git (`git rm --cached`, файлы на диске остались, изменение застейджено).

## ✅ Исправлено (2026-07-31, аудит безопасности/архитектуры)

Полный аудит rag_service на несоответствия/дубли/архитектуру/безопасность.

| # | Было | Как исправлено |
|---|---|---|
| A13 | 🔴 **Критично.** `location /documents/` в `nginx/nginx.conf` проксировал на `rag_service:8001` без единой проверки авторизации — все роуты кроме вебхука (`retrieve`, `batch-delete`, `DELETE /documents/{id}`, `reindex`, `summarize`, `ingest/upload-link`, листинг) были доступны из интернета без токена/сессии. Реальный (защищённый) путь — через `backend/admin_routes.py` (`Depends(require_admin_user)`) по внутренней докер-сети; фронтенд никогда не звал `/documents/` напрямую; вебхук MinIO бьёт в rag_service напрямую по внутренней сети, не через nginx | `location /documents/` убран из `nginx/nginx.conf` целиком — проверено, ничего легитимного не сломалось (`/admin/documents` по-прежнему 401 без токена, `/documents/retrieve` теперь 404 — падает на catch-all фронтенда, не долетает до rag_service) |
| B11 | Ручной триггер `POST /documents/{doc_id}/summarize` (кнопка «✎ Пересобрать саммари» в админке) проверял тот же `ENABLE_DOCUMENT_SUMMARIZATION`, что и авто-запуск после ingest — при выключенном флаге отвечал `202 "queued"`, но тихо ничего не делал. Флаг задуман для авто-триггера (не тратить LLM на каждый документ), а не как killswitch для осознанного ручного вызова | `task_dispatcher_service.py::dispatch_summarization` — проверка флага убрана, ручной вызов всегда диспатчит таску; заодно убран осиротевший импорт `settings`/`logging` |
| — | `POST /internal/notes/{id}/index-complete` (колбэк rag_service → backend по завершении индексации заметки) не проверял вообще ничего — доверял голому происхождению из докер-сети | Добавлен `INTERNAL_WEBHOOK_TOKEN` (тот же паттерн, что у `MINIO_NOTIFY_WEBHOOK_AUTH_TOKEN_1`) — `backend/api/notes_routes.py::index_complete` проверяет `Authorization: Bearer`, `rag_service/workers/task.py::_notify_backend_index_complete` его шлёт. Заодно закрыт `httpx.Client(...).post(...)` без `with`/`.close()` в той же функции — тёк сокет на каждый note-index |
| A14 | `get_docling_conversion_provider` — тот же незащищённый lazy-singleton (`global x; if x is None: x = ...`), что A6 чинил в `container.py::get_v_indexing_service`. Безопасно под Celery prefork (отдельные процессы), но всплыло бы при переходе на `--pool=threads/eventlet/gevent` | `worker_container.py::get_docling_conversion_provider` — тот же `threading.Lock` + double-checked locking, что и A6 |
| A15 | Qdrant payload точки саммари таблицы (`_index_table_summary`) содержал только `headers={"title": "Таблица N"}` — в отличие от точек глав (`headers={"chapter_number", "title"}`) не было структурного `table_index`, нельзя было фильтровать по номеру таблицы напрямую в Qdrant | `workers/task.py::_index_table_summary` — `headers={"title": ..., "table_index": table_index}` |
| T17 | Сравнение вебхук-токена не constant-time (`token != settings.minio_notify_webhook_auth_token_1`) — таймингового side-channel на единственный реальный секрет, который сервис проверяет | `api/rag_routes.py::handle_webhook` — `hmac.compare_digest`; заодно тот же фикс в новом `backend/api/notes_routes.py::index_complete` (появился в этой же сессии, тот же антипаттерн) |
| T18 | `s3key = f"{doc_id}/{filename}"` строился из сырого имени файла клиента — `_sanitize_filename` применялся только к значению для колонки `documents.filename`, но не к тому, что уже попало в `s3key`. Плоское S3-пространство ключей — не traversal, но display-имя и реальный MinIO-ключ могли разойтись для имён с `/`/`..` | `_sanitize_filename` перенесена из `application/document_service.py` в `domain/document.py` (правильный DDD-слой — её там и не хватало), `IngestionDocument.create_new` санитизирует ДО построения `s3key`, теперь бросает `UploadValidationError` (400) вместо голого `ValueError` (раньше падало бы в общий 500) |
| T19 | `hf_embedding_provider.py` читал `EMBEDDING_MODEL_NAME`/`HF_TOKEN` через голый `os.getenv()` — тот же антипаттерн, что A5 чинил для вебхук-токена через pydantic-settings. Подтверждено неиспользуемым (мёртвый код), но мина на будущее, если модуль снова подключат | `os.getenv`-фолбэк убран, `model`/`token` — обязательные параметры конструктора; единственный (мёртвый) caller уже передавал их явно |
| T20 | `_summarize_chapter`/`_summarize_document`/`_summarize_table` — три идентичных копии `async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))` + `except httpx.HTTPError: log+return None`, различались только URL/payload/ключом ответа | Сведены в общий `_post_summary_request(path, payload, *, log_label)`, три функции — тонкие обёртки |
| T21 | Мёртвая defensive-ветка `status=d.status.value if hasattr(d.status, "value") else str(d.status)`, задвоена в двух местах — `DocumentListItemDTO.status` это `Mapped[str]`/`String(32)`, не SQLAlchemy `Enum`, ORM всегда отдаёт `str`, `.value`-ветка никогда не срабатывала | `api/rag_routes.py:167,257` — упрощено до `status=d.status`/`status=doc.status` |
| T22 | `IngestionService.process_document` — ветка `ValueError/InvalidIngestionStateError` и финальная `except Exception` вручную повторяли одни и те же три строки (`doc.fail()`, `update_document(status=...)`, `_schedule_delayed_cleanup(doc_id)`) | Вынесены в общий `_fail_document(doc, doc_id)`, обе ветки его вызывают |
| T23 | `dispatch_reindexing` (единственный из трёх методов `TaskDispatcherService`, осознанно пропускающий проверку `status == PENDING` — см. докстринг) не был покрыт тестами вообще | Два новых теста в `test_task_dispatcher_service.py`: диспатч для уже `COMPLETED` документа (доказывает, что PENDING-гейт правда не применяется), `DocumentNotFound` для неизвестного `doc_id` |

## ✅ Исправлено (2026-08-03)

D11 (было в 🗑️ Мёртвый код) — 5 stale тест-файлов переписаны под текущий контракт, плюс попутно найден и исправлен 6-й с той же болезнью (`test_document_repository.py` — не коллектился вообще из-за отсутствующего `tests/test_db/__init__.py`, поэтому не попадал в прошлый прогон и не был в списке D11):

| Файл | Было | Стало |
|---|---|---|
| `tests/test_db/__init__.py` | Отсутствовал — `tests/test_db/` не был Python-пакетом, из-за чего оба файла внутри падали с `ModuleNotFoundError: No module named 'rag_service'` при коллекции (pytest не мог подняться до корня репозитория по цепочке `__init__.py`) | Создан пустой файл-маркер пакета |
| `test_vector_indexing_service.py` | Тестировал `upsert_points()`/`vector_provider`/`embedding_batch_size` — API, которого в `VectorIndexingService` больше нет | Переписан на `get_sparse_vectors()`/`get_hybrid_vectors()` — единственное, что не покрыто соседним `test_vector_indexing_prefixes.py` (dense-префиксы уже там) |
| `test_ingestion_service.py` | Импортировал `rag_service.workers.ingestion_service` (модуль удалён, класс переехал в `application/`), конструктор/чанкер не совпадали с текущими | Переписан под `IngestionService(document_service, vector_storage, vector_indexing_service, s3_storage, conversion_pipeline)` и `process_document()`: happy path, отсутствующая строка документа, дубликат по хешу, транзиентная ошибка (перебрасывается, статус остаётся PROCESSING для ретрая Celery), детерминированная ошибка (ERROR) |
| `test_s3/test_s3_storage.py` | `S3StorageRepository(endpoint_url=..., bucket=...)` — репозиторий давно мульти-бакетный, бакет передаётся в каждый метод | Переписан на `private_endpoint_url`/`public_endpoint_url` + `bucket` per-call против реального MinIO (`test-bucket`); добавлены тесты на `generate_presigned_download_url` (inline-просмотр) и `ensure_bucket()` — новые методы без покрытия |
| `test_db/test_integration_database_document_service.py` | Фикстура чинила схему точечными `ALTER TABLE`; `update_document()` звали именованными kwargs, которых больше нет (`update_data: dict`) | Фикстура делает `DROP SCHEMA rag_kernel CASCADE` + `create_all` (гарантированно текущая схема вместо патчей); `update_document()` вызывается через `update_data=` |
| `test_db/test_document_repository.py` | Тот же баг с `update_document()` kwargs, что и в предыдущем файле — не всплывал раньше, потому что файл не коллектился (см. `__init__.py` выше) | Один вызов переведён на `update_data=` |
| `test_integration_document_orchestrator.py` | `DocumentOrchestrator(s3_storage=S3StorageRepository(...))` — оркестратор теперь ждёт bucket-scoped `BucketStorageProvider`, не сырой мульти-бакетный репозиторий; ключи вида `documents/YYYY/MM/...__hash.ext` (regex), `chunks_total` в `get_document_info` | Локальный `_TestBucketStorage`-адаптер (аналог прод `KnowledgeBaseStorageService`, но на `test-bucket`, не на реальный `knowledge-base`); ключи `{doc_uuid}/{filename}` (T18); убран несуществующий `chunks_total`; `get_list_document` теперь проверяется как берущий `size` из Postgres `file_size`, а не живого `stat()` в S3; добавлен тест на `get_file_url()` (presigned inline-ссылка — новый метод) |
| `test_integration_upload_webhook_flow.py` | Вебхук проверялся заголовком `X-Minio-Extract-Token` + monkeypatch env — текущий роут проверяет `Authorization: Bearer <token>` через `hmac.compare_digest` против `settings.minio_notify_webhook_auth_token_1` (monkeypatch не подействовал бы — settings синглтон читается один раз при импорте) | Заголовок `Authorization: Bearer {settings.minio_notify_webhook_auth_token_1}`; собран `FastAPI` тест-апп с `register_exception_handlers` (иначе `DuplicateFilenameError`/`WebhookAuthorizationError` улетали бы как голый 500, а не 401/409); добавлены тесты на отсутствующий/неверный токен и на дубликат имени файла |

`rag_service/.env` создан локально для прогона (`MODE=TEST`, отдельная `test_myapp_db`, MinIO `test-bucket`, все хосты — `localhost`, публикуемые порты контейнеров) — не коммитится (`.gitignore`). Полный `pytest rag_service/tests` — 120/120 зелёных.

## ✅ Исправлено (2026-08-05, аудит A11-фичи + perf/security)

Точечный аудит `AbbreviationExpander` (A11, добавлен 2026-08-04) плюс общий perf/security-проход.

| # | Было | Как исправлено |
|---|---|---|
| B15 | `RetrieveService.retrieve()` вызывал `AbbreviationExpander.expand()` синхронно внутри `async def` — pymorphy3-лемматизация (чистый Python, не C-расширение) считается для каждого слова запроса безусловно (`_build_canonical`), не только при реальном совпадении с известной аббревиатурой, вопреки собственному дизайн-принципу A11 MVP ("без доп. нагрузки для обычного случая"). rag_service — один FastAPI-процесс на один event loop; `/documents/retrieve` дёргается llm_service на каждое сообщение чата (до 6 запросов за вызов) — пока один запрос лемматизируется, event loop не обслуживает остальные конкурентные retrieve/health-check | `application/retrieve_service.py:260` — вызов обёрнут в `await asyncio.to_thread(self._abbreviation_expander.expand, queries)`. Проверено: 16/16 тестов (`test_retrieve_service.py`, `test_abbreviation_expander.py`) зелёные, живой запрос `POST /documents/retrieve` с реальной аббревиатурой ("ПНР") внутри контейнера отработал корректно после `--reload` |
| B16 | `RetrieveRequest.queries` (`api/schemas.py`) ограничивал только количество элементов списка (`min_length=1`), без `max_length` ни на список, ни на отдельную строку запроса. В связке с B15 (уже без блокировки event loop, но всё ещё неограниченная работа на один запрос) — запрос с очень длинным текстом заставлял `AbbreviationExpander` лемматизировать неограниченное число слов | `api/schemas.py` — `queries: list[Annotated[str, Field(max_length=2000)]]` с `max_length=30` на сам список. Проверено живьём: запрос с 3000-символьной строкой → `422 string_too_long`; список из 31 запроса → `422 too_long` |
| A19 | `qdrant_vector_storage.py::search`/`batch_search` формировали `VectorSearchError` через `f"...{exc=}"` — repr исходного исключения Qdrant (хост/порт/детали таймаута) попадал в `exc.message`, а `exception_handlers.py` возвращает `message` как есть в теле HTTP-ответа. Соседние error-классы того же файла (`VectorUpsertError`, `VectorDeleteError`) статичные сообщения без `str(exc)`/`{exc=}` уже использовали — паттерн был локален для этих двух мест | Оба места переведены на статичное сообщение (`"Failed to execute vector search in Qdrant"` / `"...batch vector search..."`), реальная причина уходит только в серверный лог через новый `logger.exception(...)` (модуль раньше не имел логгера вообще). Проверено живьём: смоделированный `ConnectionError` с хостом/портом в тексте — в логе есть, в `exc.message` (то, что уйдёт клиенту) — нет |
| A20 | Содержимое загруженного файла не валидировалось на сервере — файл льётся клиентом напрямую в MinIO по presigned URL, минуя rag_service; проверка (`IngestionDocument.create_new`) была только по расширению из имени, до того как байты файла вообще существуют. Docling получал на layout/OCR-парсинг что угодно под заявленным `.pdf`-ключом без magic-byte проверки | Новая `domain/document.py::validate_file_content(content, filename)` — сверяет магические байты (`%PDF-` / `PK\x03\x04` для .docx) или UTF-8-декодируемость (.txt) против заявленного расширения, поднимает `UploadValidationError`. Вызывается в `ingestion_service.py::process_document` сразу после скачивания из S3, до Docling; `UploadValidationError` добавлен в нератраящуюся ветку (детерминированная ошибка → статус ERROR, не ретраится). Проверено живьём внутри контейнера на всех 3 расширениях × валидный/поддельный контент (6 случаев) — все корректны; фикстура `test_ingestion_service.py::s3_storage_mock` обновлена на реальную PDF-сигнатуру |

## ✅ Исправлено (2026-08-05, обзор обработки исключений)

Целевой проход по всему rag_service на тему исключений — где проглатываются/неверно классифицируются/теряют traceback, и где типизированного исключения не хватает или существующее не используется.

| # | Было | Как исправлено |
|---|---|---|
| — | `document_service.py::update_document_hash_atomically` — `except IntegrityError as e: ... raise e` вместо `raise` (тот же антипаттерн, что T1 уже чинил в `ingestion_service.py` — здесь пропущен) | `raise e` → `raise` |
| — | `document_service.py::create_doc` — на коллизию `doc_id` поднимал `DocumentAlreadyExists(f"Document {doc_id} already exists")`, хотя конструктор класса ждёт `file_hash` и сам строит `f"Document with hash '{file_hash}' already exists"` — получалось задвоенное бессмысленное сообщение и `self.file_hash`, реально хранящий не хеш, а doc_id. Семантически это вообще другая ситуация (коллизия id, не дубликат по содержимому) | Новый `DocumentIdConflict(doc_id)` в `domain/errors/postgres.py` (409, отдельный от `DocumentAlreadyExists`) — `create_doc` поднимает его напрямую с чистым сообщением |
| — | `document_orchestrator.py::delete_document`/`get_document_info` поднимали голый `ValueError(f"Document '{doc_id}' not found")`, хотя типизированный `DocumentNotFound` уже существует и используется в том же файле проекта (`rag_routes.py::get_document_details`). Вызывающий код (`rag_routes.py`) был вынужден ловить `except ValueError` и перезаворачивать в `DocumentNotFound` — широкий catch, который заодно перехватил бы и посторонний `ValueError` из глубины `delete_document` и ошибочно доложил бы его как "документ не найден" (404) вместо реальной 500 | Обе точки переведены на `raise DocumentNotFound(doc_id)`. `rag_routes.py::delete_document` — try/except с перезаворачиванием убран целиком; `batch_delete_documents` — `except ValueError` заменён на `except DocumentNotFound`. Тесты обновлены на `pytest.raises(DocumentNotFound)`. Проверено живьём: `DELETE /documents/{случайный_uuid}` → чистый `404`; `POST /documents/batch-delete` с несуществующим + невалидным id → `not_found`/`failed` по-прежнему корректно разделены |
| — | `workers/task.py::_post_summary_request` — докстринг явно обещает "сбой одного элемента не должен ронять обработку остальных" (best-effort саммаризация глав/таблиц), но `except httpx.HTTPError` не покрывал `response.json()` на невалидном теле ответа llm_service (`json.JSONDecodeError`, подкласс `ValueError`) или валидный JSON не-словарь (`AttributeError` на `.get`). `summarize_document_chapters_task` (`max_retries=0`, без per-item try/except вокруг вызова) в этом случае падала бы целиком, теряя саммари всех оставшихся глав/таблиц документа, а не только текущего элемента | Except расширен до `(httpx.HTTPError, ValueError, AttributeError)` — оба новых случая теперь тоже "skip and return None", как задумано |

Проверено: `pytest rag_service/tests` — 149/149 зелёных после каждого шага; ни одна из правок не расширяет и не сужает набор ошибок, которые `ingestion_service.py::process_document` классифицирует как транзиентные — риск регрессии в Celery-ретраях исключён намеренно (см. D13 в `ISSUES.md`).
