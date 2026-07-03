# RAG Service — Issues & Fixes

## 🔴 Баги

| # | Описание | Файл | Строка |
|---|---|---|---|
| B3 | `score_threshold` в `search()` не доходит до Qdrant — `query_points()` вызывается без этого kwarg (в `batch_search()` передаётся корректно, асимметрия между методами) | `infrastructures/repositories/qdrant_vector_storage.py` | 191–199 |

---

## 🟠 Архитектурные / поведенческие проблемы

| # | Описание | Файл | Строка |
|---|---|---|---|
| A1 | `_ensure_collection` вызывается при каждом upsert — лишний `collection_exists()` к Qdrant на каждый документ | `infrastructures/repositories/qdrant_vector_storage.py` | вызов 104, def 294 |
| A9 | **OOM при инжекте:** `bm25_sparse_vector` строит инвертированный индекс в RAM → Qdrant крашится и обрывает соединение. Фикс: добавить `index=models.SparseIndexParams(on_disk=True)` в `SparseVectorParams` при `create_collection`. **Важно:** требует пересоздания коллекции и переиндексации всех документов. | `infrastructures/repositories/qdrant_vector_storage.py` | 332 |
| A2 | `source` в child chunks — временный путь во `TemporaryDirectory()` (`workers/ingestion_service.py:113-120`), который удаляется сразу после ingestion | `application/chunking_pipeline.py` | 58 |
| A5 | Webhook-токен через `os.getenv` вместо `pydantic-settings` — нарушение архитектурного соглашения | `api/rag_routes.py` | 84 |
| A6 | Глобальный синглтон `v_indexing_service` без thread-safety — `if v_indexing_service is None` без lock, race condition при параллельном старте воркеров | `infrastructure.py` | 71–82 |
| A7 | Ключ дедупликации в `group_hits_by_parent` — только `parent_id`, а не `(doc_id, parent_id)` | `application/retrieve_service.py` | 217 |
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

**✅ Критерии приемки (Acceptance Criteria)**
- [ ] Созданы миграции для 4-х таблиц БД.
- [ ] Настроен клиент MinIO в приложении, созданы методы загрузки папки `scratch1/`.
- [ ] Пайплайн парсинга завершается успешным Bulk Insert в Postgres и Upload в MinIO.
- [ ] При удалении документа из `documents` через каскад стираются все связанные строки.

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