
# RAG Service — Issues & Fixes

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

---

## 🔴 Баги

| # | Описание | Файл | Строка |
|---|---|---|---|
| B3 | `score_threshold` в `search()` не доходит до Qdrant — `query_points()` вызывается без этого kwarg (в `batch_search()` передаётся корректно, асимметрия между методами) | `infrastructures/repositories/qdrant_vector_storage.py` | 191–199 |

---

## 🟠 Архитектурные / поведенческие проблемы

| # | Описание | Файл | Строка |
|---|---|---|---|
| A1 | `_ensure_collection` вызывается при каждом upsert — лишний `collection_exists()` к Qdrant на каждый документ. ⚠️ Частично смягчено: вызов теперь под `asyncio.Lock` (строка 78/295) — race condition из исходного описания устранена, но сам round-trip `collection_exists()` на каждый upsert остаётся | `infrastructures/repositories/qdrant_vector_storage.py` | вызов 104, def 294 |
| A9 | **OOM при инжекте:** `bm25_sparse_vector` строит инвертированный индекс в RAM → Qdrant крашится и обрывает соединение. Фикс: добавить `index=models.SparseIndexParams(on_disk=True)` в `SparseVectorParams` при `create_collection`. **Важно:** требует пересоздания коллекции и переиндексации всех документов. | `infrastructures/repositories/qdrant_vector_storage.py` | 332 |
| A5 | Webhook-токен через `os.getenv` вместо `pydantic-settings` — нарушение архитектурного соглашения | `api/rag_routes.py` | 84 |
| A6 | Глобальный синглтон `v_indexing_service` без thread-safety — `if v_indexing_service is None` без lock, race condition при параллельном старте воркеров. Файл переехал (`infrastructure.py` → `container.py` в рамках более позднего рефакторинга), баг всё ещё актуален на новом месте | `container.py` | 80–91 |
| A7 | Ключ дедупликации в `group_hits_by_parent` — только `parent_id`, а не `(doc_id, parent_id)`. Усугубляется тем, что docstring/тайп-хинт `batch_search()` (строки 126, 150) заявляют ключ `(doc_id, parent_id)`, а по факту используется голый `parent_id` — аннотация врёт | `application/retrieve_service.py` | 217 |
| A8 | `DocumentStatus` определён в `api/schemas.py` — импортируют напрямую `domain/document.py`, `models/models.py`, `application/task_dispatcher_service.py` | `api/schemas.py` | 8–23 |
| A10 | Реструктуризация хранения документов — гибридная архитектура PostgreSQL + MinIO. Детали ниже ⬇️ | — | — |
| A11 | Обработка сокращений (аббревиатур) — отдельно от таблиц, нужна нормализация/расшифровка перед индексацией и поиском | — | — |

---

### 📦 A10 — Реализация гибридной архитектуры хранения документов (PostgreSQL + MinIO)

**🎯 Цель**
Организовать надежное и масштабируемое хранение структурированных результатов парсинга (Markdown-глав, таблиц, метаданных) согласно разработанному пайплайну Docling. Разделить хранение тяжелых бинарных/текстовых файлов и легких реляционных связей.

**🏛️ Архитектурный паттерн**
- MinIO (S3): Хранилище «сырых» и обработанных файлов. Файлы изолируются в бакете по UUID документа.
- PostgreSQL: Индексный навигатор. Хранит структуру документа, метаданные, JSONB-копии таблиц и текстовые саммари от LLM. Сами файлы целиком в БД не сохраняются.

**📂 0. Схема бакетов (домены, не сущности)**

Вместо бакета на каждый документ/пользователя/проект — 3 доменных бакета, изоляция внутри по папке-префиксу:

| Бакет | Папка внутри | Назначение |
|---|---|---|
| `knowledge-base` | `{doc_uuid}/...` | База знаний — ГОСТы и прочие документы (см. п.1 ниже) |
| `users` | `{user_id}/...` | Личные файлы пользователей (аватары и т.п.) |
| `projects` | `{project_id}/...` | Файлы проектов (Фича 5, `TODO.md`) |

Версионирование и lifecycle-политики настраиваются на уровне бакета — при таком подходе они общие для всех документов/проектов/пользователей внутри домена (не per-сущность). Если понадобится точечная политика — MinIO поддерживает lifecycle rules с ограничением по префиксу.

**📂 1. Структура объектов в MinIO (S3) — бакет `knowledge-base`**

```
[UUID-документа]/
├── 125.pdf                  # Исходный оригинал
├── 125.json / .doctags      # Сырые бэкапы Docling (для репарсинга)
├── 125.md / 125.txt         # Полные очищенные текстовые форматы
├── 125_toc.md / _abbrev.md  # Оглавление и словарь сокращений
├── chapters/
│   └── chapter_N.md         # Нарезанные файлы глав (основа для RAG)
└── tables/
    ├── table_N.csv          # Для скачивания инженерами
    └── table_N.html         # Для быстрого рендера на фронте
```

**🏛️ 2. Схема таблиц в PostgreSQL (DDL)**
- `documents` — главная карточка документа (`id UUID`, `filename`, `title`, `s3_prefix`).
- `document_chapters` — навигация по главам (`doc_id`, `chapter_number`, `title`, `s3_md_path`, `summary TEXT` от LLM).
- `document_tables` — индекс таблиц (`doc_id`, `table_index`, `title`, `s3_csv_path`, `s3_html_path`, `raw_json JSONB` — для сборки в Excel через Pandas «на лету»).
- `document_meta_sections` — служебные разделы (`doc_id`, `section_type` [TOC/ABBREVIATIONS/APPENDICES], `s3_md_path`).

⚠️ Важно: для всех дочерних таблиц настроить `ON DELETE CASCADE` по ключу `doc_id` для чистого каскадного удаления данных.

**🔄 3. Алгоритм работы Celery-воркера (после Этапа 5)**
1. Создать запись в `documents`, сгенерировать UUID.
2. Загрузить все локальные файлы из `scratch1/` в MinIO, подставив UUID в путь.
3. Записать структуру глав, мета-разделов и метаданные таблиц в Postgres. В `raw_json` таблицы упаковать через Pandas (`df.to_json(orient="split")`).
4. Отправить текст глав в LLM-воркер для асинхронной генерации кратких summary.

**✅ Критерии приемки (Acceptance Criteria) — статус на 2026-07-17**
- [~] Миграции для 4-х таблиц БД — миграций (Alembic и т.п.) вообще нет, схема живёт только в `models/models.py`. И реализовано только **3 из 4** таблиц: `documents`, `document_chapters`, `document_tables`. `document_meta_sections` не создана — мета-разделы (TOC, аббревиатуры) заливаются в S3 (`ingestion_service.py:379-386`), но без индекса в Postgres.
- [x] Настроен клиент MinIO в приложении — `S3StorageRepository` работает; концепция `scratch1/` как локального стейджинга упразднена целиком (пайплайн работает с bytes в памяти, без временных файлов) — критерий выполнен по духу, не буквально.
- [x] Пайплайн парсинга завершается успешным Bulk Insert в Postgres и Upload в MinIO — подтверждено (`ingestion_service.py:284-297`, `_store_docling_artifacts`).
- [x] При удалении документа из `documents` через каскад стираются все связанные строки — подтверждено, `ondelete="CASCADE"` + `cascade="all, delete-orphan"` на всех child-таблицах (`models/models.py:47-61,76,100,122`).
- [ ] Не в исходном списке, но часть замысла A10: `document_tables`/`document_chapters.summary` — колонка `summary` существует, но никогда не заполняется (LLM-саммари по главам/таблицам не реализовано, см. `PARSING_TABLES_PLAN.md`).

---

## 🟡 Типы / стиль / неточности

| # | Описание | Файл | Строка |
|---|---|---|---|
| T2 | Deprecated: `List`, `Dict` вместо `list`, `dict` из built-ins | `application/ingestion_service.py` | 9 |
| T6 | Misleading переменная `existing_by_name` — проверка идёт по `doc_id`, а не по имени | `application/document_service.py` | ~125 |
| T7 | Аннотация `status: str` вместо `status: DocumentStatus` | `application/document_service.py` | ~57 |
| T8 | `requested_parent_ids` — передаются строки, `get_parent_chunks` ожидает `list[uuid.UUID]` | `application/retrieve_service.py` | 105, 164 |
| T9 | `BatchDeleteDocumentsResponse.failed` — роут собирает `list[dict]`, схема ожидает `list[BatchDeleteErrorItem]` (рантайм не ломается — pydantic коэрсит dict в модель при конструировании) | `api/rag_routes.py:173,188`, `api/schemas.py:127` | — |
| T11 | `GET /documents` использует write-сервис (`DocServiceDep`) вместо read-only `DocQueryServiceDep` | `api/rag_routes.py` | 125 |
| T12 | `GET /documents` без `response_model` — схема `DocumentSummaryResponse` есть (`api/schemas.py:66`), но не подключена | `api/rag_routes.py` | 123 |
| T13 | `PlaceholderActionResponse.detail` — обязательное поле без дефолта (используется только внутри закомментированных роутов D1, поэтому в рантайме не стреляет) | `api/schemas.py` | 133 |

---

## 🗑️ Мёртвый код

| # | Описание | Файл | Строка |
|---|---|---|---|
| D1 | ~180 строк закомментированных роутов (`/documents/{doc_id}/status`, detail, `/admin/storage/files*`, placeholder-роуты) | `api/rag_routes.py` | 94–275 |
| D4 | `dispatch_reindexing()` пустой stub | `application/task_dispatcher_service.py` | 25–29 |
| D6 | `update_metadata_document()` пустой stub (`pass`) | `application/document_service.py` | 198–199 |
| D7 | `set_status()` дублирует `update_document()`; в проде вызывается только изнутри самого сервиса, воркер (`ingestion_service.py`) использует исключительно `update_document()`. Вызывается лишь из тестов | `application/document_service.py` | 160–169 |
| D8 | `RequestLoggingMiddleware` — оба ветки `dispatch()` просто вызывают `call_next` и возвращают результат, ничего не логируют и не замеряют. Название вводит в заблуждение — выглядит как логирование запросов, по факту no-op прогонка через лишний слой `BaseHTTPMiddleware` на каждый запрос | `main.py` | 23–29 |