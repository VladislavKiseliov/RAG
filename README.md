# RAGProgramm

Локальный корпоративный AI-ассистент поверх внутренней документации компании — с личными
заметками, корпоративным мессенджером и админ-панелью в одном self-hosted приложении.
Разворачивается полностью внутри инфраструктуры компании, без внешних облачных зависимостей
(кроме самого LLM-провайдера, который тоже настраивается на self-hosted вариант).

---

## Что это

Сотрудник заходит в один веб-интерфейс и получает:

- **AI-чат**, который отвечает по внутренней документации (регламенты, инструкции, ГОСТы) с
  указанием источника — не «где-то читал», а конкретный документ/глава/таблица;
- **Базу знаний** с полнотекстовой читалкой документов (главы, таблицы, гибридный поиск);
- **Личные заметки** — набросал мысль голосом/текстом, ИИ сам оформил в аккуратную заметку с
  заголовком, структурой и тегами;
- **Корпоративный мессенджер** — обычные личные чаты с коллегами, реалтайм через WebSocket;
- **Проекты** и **задачи на день** — координация работы команды (в разработке);
- **Админ-панель** — документы, пользователи, мониторинг фоновых задач, состояние сервисов.

---

## Возможности

### ✅ Готово

- **AI-чат с гибридным RAG-поиском** — LangGraph-агент (planner-first: LLM сама решает по
  вопросу, нужен ли поиск по базе и как его сформулировать), dense + BM25 поиск с
  DBSF-fusion по Qdrant, реранк кросс-энкодером, контролируемая рефлексия при слабом
  результате (до 1 доп. круга поиска), честный отказ вместо выдумки, если в базе ничего
  не нашлось, ответ со ссылкой на источник (документ / глава / таблица)
- **База знаний** — загрузка документов (PDF/DOCX/MD), парсинг через Docling с сохранением
  структуры (главы, таблицы), полноэкранная читалка
- **Заметки с AI-генерацией** — сырой поток мыслей → структурированный Markdown одним запросом к
  LLM, который сразу же определяет заголовок, теги, папку и дату напоминания (строгий JSON-ответ,
  без отдельного агента — просто один хорошо спроектированный промпт)
- **Корпоративный мессенджер** — личные чаты, реалтайм через WebSocket (доставка сообщений,
  индикатор «печатает», статус прочтения), поиск коллег для нового чата
- **Ролевая модель** (`is_superuser`) — гейтинг админских разделов и API
- **Админ-панель** — пользователи (роли, блокировка), документы (загрузка, реиндексация,
  удаление), состояние всех сервисов онлайн, мониторинг фоновых задач Celery через Flower
  (список, статусы, отмена зависшей задачи)

### 🚧 В разработке

- **Проекты** — на фронте есть экран, бэкенда с реальным хранением пока нет
- **Задачи на день / Главная (дашборд)** — экраны собраны на моках, бэкенда нет
- Мессенджер: пагинация истории сообщений (бэкенд уже поддерживает, фронт пока грузит только
  последнюю страницу)

### 📋 Запланировано

- **AI как участник мессенджер-чата** (`@gpt`) — бот отвечает на упоминание прямо в чате
- **AI-аудит опросных листов на соответствие ГОСТам** — батчевая сверка технического задания
  (до 100+ страниц) с нормативной базой в Qdrant, отчёт по несоответствиям
- **Отложенные push-уведомления** — напоминания из заметок/задач приходят даже при закрытом
  браузере (RabbitMQ delayed exchange + Web Push)
- Автосаммари переписки по счётчику сообщений

Актуальный приоритетный план и известные баги — в [`TODO.md`](TODO.md); архитектурный долг
`rag_service` — в [`rag_service/ISSUES.md`](rag_service/ISSUES.md).

---

## Сервисы

| Сервис | Порт | Описание |
|---|---|---|
| `backend` | 8000 | Единая точка входа: auth, чаты, мессенджер (REST + WS), заметки, admin-proxy |
| `rag_service` | 8001 | Индексация и поиск документов/заметок, webhook MinIO |
| `llm_service` | 8002 | Генерация ответов и заметок через LangGraph RAG-агент |
| `frontend` | 5173 | Основной UI: чат, мессенджер, база знаний, заметки, проекты, встроенная админ-панель |
| `rag-worker` | — | Celery-воркер: парсинг, чанкинг, векторизация документов и заметок |
| `PostgreSQL` | 5432 | Метаданные: документы, чаты, пользователи, заметки |
| `Qdrant` | 6333 | Векторный индекс (гибридный поиск), отдельные коллекции для документов и заметок |
| `MinIO` | 9000 | S3-хранилище файлов + webhook при загрузке |
| `Redis` | 6379 | Брокер задач для Celery |
| `Flower` | 5555 | Мониторинг и отмена задач Celery (используется и напрямую, и через админ-панель) |

---

## Архитектура

```mermaid
graph TB
    User["Frontend (чат / мессенджер / заметки)"] --> B["backend :8000"]
    Admin["Admin Panel"] --> B
    B -->|"ask / generate note"| L["llm_service :8002"]
    L -->|"retrieve context"| R["rag_service :8001"]
    B -->|"docs proxy, index note"| R
    B -->|"task monitoring"| F["Flower :5555"]
    R --> PG["PostgreSQL"]
    R --> Q["Qdrant (hybrid)"]
    R --> M["MinIO"]
    R --> RD["Redis"]
    RD --> W["Celery Worker"]
    W --> M
    W --> PG
    W --> Q
    M -->|"webhook"| R
    F --> RD
```

### Поток загрузки и индексации документа

```mermaid
sequenceDiagram
    autonumber
    participant Admin as Admin Panel
    participant BE as Backend
    participant RAG as RAG API
    participant S3 as MinIO
    participant Redis
    participant W as Celery Worker
    participant PG as Postgres
    participant Q as Qdrant

    Admin->>BE: запрос на загрузку файла
    BE->>RAG: POST /documents/ingest/upload-link
    RAG->>PG: создать запись документа (PENDING)
    RAG->>S3: сгенерировать presigned PUT URL
    RAG-->>BE: doc_id + presigned_url
    BE-->>Admin: URL для загрузки

    Admin->>S3: PUT файл напрямую
    S3->>RAG: webhook (object created)
    RAG->>PG: статус → QUEUED
    RAG->>Redis: enqueue(doc_id, key)

    Redis->>W: задача на обработку
    W->>S3: скачать файл
    W->>W: парсинг → чанкинг → embed (LocalEmbeddingProvider)
    W->>PG: сохранить чанки, статус → SUCCESS
    W->>Q: upsert dense_vector + bm25_sparse_vector
```

### Поток ответа на вопрос

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant BE as Backend
    participant LLM as LLM Service (граф агента)
    participant RAG as RAG Service
    participant Q as Qdrant

    FE->>BE: POST /api/chats/{id}/messages/stream
    BE->>LLM: POST /llm/answer/stream {query, history, summary}
    LLM->>LLM: plan — LLM решает: нужен ли поиск, какими формулировками
    alt поиск нужен (route=domain_rag)
        LLM->>RAG: POST /documents/retrieve {queries[]} (тул search_docs)
        RAG->>Q: batch hybrid search (dense + BM25, DBSF fusion)
        Q-->>RAG: top chunks
        RAG-->>LLM: parent chunks + sources
        LLM->>LLM: rerank — кросс-энкодер пересортировывает
        opt слабый/пустой результат
            LLM->>LLM: reflect — уточнить запрос и повторить поиск (до 1 раза) либо честный отказ
        end
    else поиск не нужен (route=smalltalk)
        Note over LLM: сразу к generate с диалоговым промптом
    end
    LLM->>LLM: generate — потоковый ответ (SSE) либо no_data
    LLM-->>BE: answer + sources (потоком)
    BE-->>FE: answer + sources (потоком)
```

Полная схема графа (все ноды, промпты, статус каждого инструмента) — построчно сверена с
кодом в [`llm_service/AGENT_GRAPH_CURRENT.md`](llm_service/AGENT_GRAPH_CURRENT.md).

### Поток генерации и индексации заметки

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant BE as Backend
    participant LLM as LLM Service
    participant RAG as RAG Service
    participant Q as Qdrant

    FE->>BE: POST /api/notes/{guid}/generate {raw_text}
    BE->>LLM: POST /llm/note {raw_text}
    LLM->>LLM: строгий JSON-промпт: title, content, tags, folder, reminder
    LLM-->>BE: сгенерированная заметка
    BE->>BE: сохранить в Postgres
    BE-->>FE: обновлённая заметка

    FE->>BE: POST /api/notes/{guid}/index
    BE->>RAG: POST /notes/{guid}/index {text}
    RAG->>RAG: Celery: чанкинг + embed
    RAG->>Q: upsert в notes_collection
    RAG-->>BE: POST /internal/notes/{guid}/index-complete
    BE->>BE: статус → indexed
```

---

## Поиск (Hybrid RAG)

1. **Формулировка запроса** — не отдельный LLM-шаг «расширения»: `plan`-нода агента сама
   решает, какими 1-3 формулировками искать (часть JSON-ответа планировщика), исходя из
   вопроса и истории диалога
2. **Batch hybrid search** — для каждой формулировки параллельный prefetch:
   - Dense: `dense_vector` (multilingual-e5-large, cosine)
   - Sparse: `bm25_sparse_vector` (серверный `qdrant/bm25`)
   - Fusion: **DBSF** (Distribution-Based Score Fusion)
3. **Parent chunk retrieval** — по найденным дочерним чанкам достаём родительский контекст из Postgres
4. **Rerank** — кросс-энкодер (`bge-reranker-v2-m3`, отдельный TEI-контейнер) пересортировывает
   пул по лучшему child-чанку каждого родителя, калиброванный score определяет, хватает ли
   контекста для ответа или нужен ещё один круг поиска (`reflect`)

Документы и заметки индексируются в отдельные коллекции Qdrant через общий переиспользуемый
клиент (`QdrantVectorStorage`), но одной и той же гибридной схемой поиска.

---

## LLM Pipeline (LangGraph)

`llm_service` использует LangGraph-агент (`LeanRagAgent`), planner-first — без ML-роутера
и без отдельного шага расширения запроса, один путь для всех вопросов:

1. `plan` — LLM (JSON-контракт) решает по вопросу+истории: искать ли по базе (`search_docs`
   с 1-3 формулировками), запросить ли приложение конкретного документа (`get_appendix`),
   или ответить сразу из истории без похода в базу
2. `execute_subtasks` — код-диспетчер вызывает выбранные `plan`-ом инструменты из реестра
3. `rerank` — кросс-энкодер пересортировывает найденные чанки (только если был `search_docs`)
4. `reflect` — при слабом/пустом результате LLM решает: уточнить запрос и повторить поиск
   (максимум 1 доп. круг) или честно отказаться, не выдумывая ответ
5. `no_data` — терминальный честный отказ (не дошло до `generate`)
6. `build_prompt` — сборка финального контекста
7. `generate` — потоковый ответ (SSE)
8. `extract_sources` — источники для фронта (документ / глава / таблица)
9. `post_actions` — если в вопросе есть маркер действия («сохрани», «создай задачу») —
   пока заглушка, см. [`TODO.md`](TODO.md) Фаза 7

Отдельно, вне графа — точечный эндпоинт `POST /llm/note` для генерации заметок: не требует
поиска по базе знаний, просто структурирует сырой текст в строгий JSON одним вызовом.

Полная построчная сверка с кодом (промпты, реестр инструментов, что реально работает vs
заглушка) — [`llm_service/AGENT_GRAPH_CURRENT.md`](llm_service/AGENT_GRAPH_CURRENT.md).
Целевая (пока не полностью реализованная) архитектура — [`llm_service/ARCHITECTURE.md`](llm_service/ARCHITECTURE.md).

---

## Быстрый старт

```bash
cp .env.example .env
# Заполнить обязательные поля (помечены # ⬅ заполнить):
# POSTGRES_PASSWORD, MINIO_ACCESS_KEY, MINIO_SECRET_KEY,
# MINIO_NOTIFY_WEBHOOK_AUTH_TOKEN_1, INTERNAL_WEBHOOK_TOKEN (любые строки, совпадают между сервисами),
# SECRET_KEY, HF_TOKEN, LLM_API_KEY, LLM_BASE_URL

docker compose -f docker-compose.full.yml up -d --build
```

Проверить статус:
```bash
docker compose -f docker-compose.full.yml ps
docker compose -f docker-compose.full.yml logs -f backend
```

`backend`/`llm_service`/`rag_service` смонтированы volume'ом — после правки кода достаточно
`docker compose restart <service>`, пересборка образа не нужна. `frontend` собирается на этапе
сборки образа (`npm run build` внутри `Dockerfile`) — после правки нужен `docker compose build frontend`.

---

## API

### Backend (`:8000`)

**Auth**
- `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`

**AI-чаты**
- `POST /api/chats`, `GET /api/chats`, `GET /api/chats/{chat_guid}`
- `POST /api/chats/{chat_guid}/messages` — обычный (не потоковый) ответ
- `POST /api/chats/{chat_guid}/messages/stream` — SSE-стриминг ответа (реальный живой путь фронта)
- `GET /api/chats/sources/{parent_id}` — полный текст источника по требованию (история отдаёт sources урезанными)
- `PATCH /api/chats/{chat_guid}/rename`, `DELETE /api/chats/{chat_guid}`

**Мессенджер** (REST для чатов и истории, отправка/typing/read-receipts — только через WebSocket)
- `GET /messenger/chats/`, `POST /messenger/chats/direct`, `DELETE /messenger/chats/{guid}`
- `GET /messenger/chats/{guid}/messages`
- `WS /websocket/ws/?token=` — `new_message`/`user_typing`/`message_read` от клиента,
  `new`/`new_chat_created`/`message_read`/`user_typing`/`chat_deleted` от сервера

**Заметки**
- `POST /api/notes`, `GET /api/notes`, `GET /api/notes/{guid}`
- `PATCH /api/notes/{guid}`, `DELETE /api/notes/{guid}`
- `POST /api/notes/{guid}/generate` — сгенерировать title/content/tags/folder/reminder через LLM
- `POST /api/notes/{guid}/index` — векторизовать в rag_service

**База знаний** (proxy в rag_service — кроме отмеченного ниже)
- `GET /api/knowledge/documents`, `GET /api/knowledge/documents/{id}`
- `GET /api/knowledge/documents/{id}/chapters/{n}`
- `POST /api/knowledge/documents`, `PATCH /api/knowledge/documents/{id}` — ⚠️ пока in-memory
  заглушка, не реальный ingestion (см. [`TODO.md`](TODO.md) Фаза 2)

**Admin** (весь роутер гейтится `require_admin_user`, 403 без `is_superuser`)
- `GET /admin/users/repo`, `GET /admin/users/repo/{id}`, `POST /admin/users/repo`
- `PATCH /admin/users/repo/{id}/role`, `DELETE /admin/users/repo/{id}`
- `GET /admin/documents`, `GET /admin/documents/{id}`, `GET /admin/documents/{id}/status`
- `POST /admin/documents/upload-link`, `POST /admin/documents/batch-delete`
- `DELETE /admin/documents/{id}`, `POST /admin/documents/{id}/reindex`, `POST /admin/documents/{id}/summarize`
- `POST /admin/documents/bulk-reindex`, `POST /admin/documents/bulk-summarize` — массовые операции по отфильтрованному списку
- `GET /admin/documents/{id}/download`
- `GET /admin/tasks`, `POST /admin/tasks/{task_id}/revoke` — мониторинг/отмена задач Celery (proxy в Flower)
- `GET /admin/system/health` — статус всех сервисов (rag_service через `/openapi.json`, остальные — свои probes)

### RAG Service (`:8001`)
- `POST /documents/retrieve` — batch hybrid search (вызывается тулом `search_docs` агента)
- `POST /documents/ingest/upload-link`, `POST /documents/ingest/webhook` — presigned upload + MinIO webhook
- `GET /documents`, `GET /documents/{doc_id}`, `DELETE /documents/{doc_id}`, `POST /documents/batch-delete`
- `POST /documents/{doc_id}/reindex`, `POST /documents/{doc_id}/summarize`
- `GET /documents/{doc_id}/chapters/{chapter_idx}` — текст главы + связанные таблицы (для читалки)
- `GET /documents/{doc_id}/appendices` — приложения документа (тул `get_appendix` агента)
- `GET /parent-chunks/{parent_id}` — полный текст источника по требованию
- `POST /notes/{note_id}/index`, `DELETE /notes/{note_id}/vectors`

Отдельного `/health` у rag_service нет — админка проверяет живость через `/openapi.json`
(`backend/api/admin_routes.py`).

### LLM Service (`:8002`)
- `POST /llm/answer` — обычный (не потоковый) ответ
- `POST /llm/answer/stream` — SSE-стриминг (реальный живой путь, вызывается backend'ом)
- `POST /llm/summary` — саммари переписки по счётчику сообщений
- `POST /llm/note` — генерация заметки (строгий JSON: title/content/tags/folder/reminder)
- `POST /llm/chapter-summary`, `POST /llm/document-summary`, `POST /llm/table-summary` —
  саммари главы/документа/таблицы (используются rag_service'ом при инжесте)
- `GET /llm/health`

---

## Миграции

```bash
alembic -n users upgrade head
alembic -n rag upgrade head
```

---

## Тесты

```bash
pytest rag_service/tests -q
pytest backend/tests -q
pytest llm_service/tests -q
```

Архитектура тестов (пирамида unit/integration/e2e, testcontainers, что проверять всегда) —
[`TESTING.md`](TESTING.md).

---

## Структура репозитория

```
backend/          — FastAPI: auth, чаты, мессенджер, заметки, admin proxy
rag_service/      — ingestion, retrieval, Qdrant, MinIO webhook
llm_service/      — LangGraph RAG agent (planner-first), генерация заметок
frontend/         — React UI: чат, мессенджер, база знаний, заметки, проекты, админка
migrations/       — Alembic (users, rag)
docker-compose.full.yml
.env.example
```