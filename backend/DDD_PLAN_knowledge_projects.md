# План: перевод «Базы знаний» и «Проектов» на DDD-слой

Статус на 2026-07-17: **частично реализовано, но не через выделенный DDD-слой** — `backend/api/stub_routes.py`
всё ещё существует и хостит оба роутера напрямую (никакого `RagClient`/`knowledge_routes.py` не заведено).
Внутри стаба, однако, `GET /api/knowledge/documents` и `GET .../{doc_id}` уже проксируют реальные данные
`rag_service` (список + детали + главы), а не in-memory-заглушку, как было на момент написания плана —
см. статус по доменам ниже. `/api/projects` остаётся полностью in-memory-заглушкой (`_PROJECTS`, hardcoded).

Ссылки на уже принятые решения, которые этот план обязан учитывать:
- `rag_service/ISSUES.md` → A10 (гибридное хранение PostgreSQL + MinIO, 3 доменных бакета: `knowledge-base`, `users`, `projects`)
- `TODO.md` → Фича 1 (тег `category` в payload чанка), Фича 5 (Управление проектами)
- `CLAUDE.md` → сервисная карта: только `rag_service` трогает Postgres(rag)/Qdrant/MinIO напрямую; `backend` — proxy

---

## Ключевое архитектурное решение: где живёт «База знаний»

Документы — это уже домен `rag_service` (`domain/document.py`, `application/document_service.py`,
`infrastructures/repositories/document_repository.py`), с собственной DDD-структурой и таблицами Postgres.
Заводить вторую копию «документов» в backend — дублирование домена, прямое нарушение раздела Architecture
из `CLAUDE.md`.

**Решение: `backend` не хранит документы. `backend/api/knowledge_routes.py` — тонкий proxy-слой к `rag_service`,
по образцу `LLMClient` (`backend/services/ai/llm_client.py`) — httpx-клиент по `service_url` из настроек.**

Из этого следует, чего в `rag_service` пока не хватает и что нужно туда добавить (не в backend):
| Нужно для UI | Есть в rag_service сейчас | Действие |
|---|---|---|
| `collection` (api/infra/process) | Нет поля тегов на документе | Добавить `category: str \| None` в `documents` — уже запланировано в Фиче 1 |
| `personal` / владелец документа | Нет `owner_user_id` | Добавить поле в `documents`, заполнять из JWT при аплоаде через backend |
| `summary`, `sections[]` (краткое по документу и главам) | Спроектировано, но не реализовано — см. A10 (`document_chapters.summary`) | Реализовать A10 прежде, чем строить `sections` в UI на реальных данных |
| `chunk_size`, `overlap`, `model`, `dim`, `metric` | Известны на этапе индексации, не сохраняются как метаданные документа | Сохранять при ingestion в `documents` или `document_chapters` |

Если реализация A10 в rag_service отстаёт по времени от фронта — backend может первое время отдавать
`sections: []` и `summary: null`, не блокируя список документов и статус индексации (это уже полностью
покрыто существующим API rag_service: `GET /documents`, `POST /documents/ingest/upload-link`, webhook).

---

## Домен 1: База знаний (`backend/api/knowledge_routes.py`)

**Статус на 2026-07-17:**
- ✅ Реальные чтения: `list_documents`/`GET .../{doc_id}` и проксирование глав (`GET .../chapters/{n}`) уже берут данные из `rag_service` (`stub_routes.py:102-115,274-282`) — план описывал это как ещё не сделанное.
- ❌ Выделение в `RagClient`/`knowledge_routes.py` — не сделано, всё ещё внутри `stub_routes.py`.
- ❌ Upload/patch документа — всё ещё in-memory `_DOCUMENTS` (`stub_routes.py:42,252-271,285-294`).
- ❌ `category`, `owner_user_id` на документе — не добавлены в `rag_service`.

Слой в backend минимальный — авторизация, маппинг ответа rag_service под контракт фронта, ничего доменного:

```
backend/
  services/rag/
    rag_client.py          # httpx-клиент к rag_service, аналог LLMClient
  api/
    knowledge_routes.py    # заменяет knowledge_router из stub_routes.py
```

- `RagClient.list_documents(category, owner_user_id) -> list[DocumentSummary]`
- `RagClient.upload_document(file, owner_user_id) -> DocumentSummary` — грузит через существующий флоу
  `upload-link` → PUT в MinIO → дождаться webhook, либо (проще для MVP) rag_service получает отдельный
  синхронный `POST /documents` для небольших личных файлов
- `RagClient.get_document(doc_id) -> DocumentDetail` (с `sections`, когда A10 будет готов)

`DocumentServiceDep` в `backend/dependencies.py` регистрируется так же, как `ConversationServiceDep`
(конструктор принимает `container.rag_client`, а не `session_factory` — своей БД у этого сервиса нет).

Фронт (`useKnowledgeBase.js`) не меняется — контракт `ENDPOINTS.KNOWLEDGE_DOCUMENTS` тот же, меняется только
бэкенд за ним.

---

## Домен 2: Проекты (`backend/domain проекта`)

**Статус на 2026-07-17: ❌ не начато.** `_PROJECTS` в `stub_routes.py:117-243` — hardcoded список, `projects_router`
просто отдаёт его (line 297-299). Ни `models`, ни `project_repository.py`, ни `project_service.py`,
ни `project_routes.py`, ни миграции `projects_schema` не существуют.

В отличие от документов, «Проекты» — новый домен, которого нет ни в одном сервисе. Здесь нужен полноценный
DDD-слой в backend, по образцу `Chats` (`models/database_models.py` → `repository/chat_repository.py` →
`services/chat_service.py` → `api/chats_routes.py`, все через `UnitOfWork`).

### Модель предметной области

Новая схема Postgres `projects_schema` (по аналогии с `users_shema`):

| Таблица | Поля | Примечание |
|---|---|---|
| `projects` | `id`, `guid`, `name`, `desc`, `status`(enum: planning/active/review), `deadline`, `chat_id`, `created_by_id`, timestamps | `chat_id` — FK на `chats.id` (Фича 5: «общий чат — надстройка над мессенджером»), чат создаётся как `ChatType.GROUP` при создании проекта |
| `project_members` | `project_id`, `user_id`, `role`(text) | M2M, как `chat_participant` |
| `project_tasks` | `id`, `project_id`, `title`, `done`, `assignee_id`, `position` | `position` для сортировки в списке |
| `project_files` | `id`, `project_id`, `rag_doc_id`(nullable UUID), `filename`, `size_bytes`, `uploaded_by_id`, `created_at` | Если файл проиндексирован в rag_service — `rag_doc_id` заполнен и файл ищется через RAG с фильтром по `doc_id` (Фича 5); если это просто вложение — `rag_doc_id IS NULL`, хранится в бакете `projects` напрямую |
| `project_activity` | `id`, `project_id`, `actor_id`, `text`, `created_at` | Лог событий, генерируется сервисом при task/file/member-мутациях, не отдельный API |

### Слои

```
backend/
  models/database_models.py        # + Project, ProjectMember, ProjectTask, ProjectFile, ProjectActivity
  repository/
    project_repository.py          # BaseRepository, как chat_repository.py
  services/
    project_service.py             # UnitOfWork, как chat_service.py
  api/
    project_routes.py              # заменяет projects_router из stub_routes.py
  schemas/
    schemas.py                     # + ProjectSummarySchema, ProjectDetailSchema, TaskSchema...
```

- `UnitOfWork` (`services/unit_of_work.py`) получает свойство `projects -> ProjectRepository`
- `dependencies.py` получает `get_project_service` + `ProjectServiceDep`, по образцу `get_chat_service`
- Создание проекта → в одной транзакции: `INSERT project` + `INSERT chats(chat_type=GROUP)` + `INSERT project_members` для создателя. Это единственное место, где домен «Проекты» напрямую трогает домен «Чаты» — делать через `uow.chats` и `uow.projects` в одном `UnitOfWork`, не через HTTP.
- Загрузка файла в проект (`addFile` в `useProjects.js`) → `ProjectService` решает: если файл должен попасть в RAG (документ, а не просто вложение) — вызывает `RagClient.upload_document`, сохраняет `rag_doc_id`; иначе кладёт в MinIO-бакет `projects/{project_id}/...` напрямую (нужен свой S3-клиент в backend либо ещё один тонкий endpoint в rag_service `POST /storage/projects/{id}/files` — решить на этапе реализации, не блокирует остальной план).

---

## Фронт: что меняется после перехода на реальный бэкенд

- `useKnowledgeBase.js`, `useProjects.js` — контракты эндпоинтов не меняются, но пропадают поля-заглушки
  (`sections` может прийти пустым, пока не готов A10) — компонентам (`KnowledgeBasePage.jsx`,
  `DocumentCard.jsx`) нужно аккуратно обработать `sections: []` / `summary: null`, сейчас они рассчитаны на
  всегда заполненный мок.
- `ProjectsPage.jsx` — `toggleTask` и `addFile` сейчас чисто локальный `setState` в `useProjects.js`;
  после перехода это должны стать `POST/PATCH`-запросы к `project_routes.py`, иначе изменения не переживут
  обновление страницы.

---

## Порядок работ

1. `rag_service`: добавить `category`, `owner_user_id` в `documents` (маленький шаг, не весь A10)
2. `backend`: `RagClient` + `knowledge_routes.py`, убрать `knowledge_router` из `stub_routes.py`
3. `backend`: миграция для `projects_schema` (5 таблиц выше)
4. `backend`: `ProjectRepository` → `ProjectService` → `project_routes.py`, убрать `projects_router` из `stub_routes.py`
5. Когда обе части готовы — удалить `backend/api/stub_routes.py` целиком и его `include_router` в `main.py`
6. `rag_service` A10 (summary по главам, `sections`) — отдельный кусок работы, не блокирует пункты 1–5

## Критерии приёмки

- [ ] `stub_routes.py` удалён, роуты работают на реальных таблицах/rag_service
- [~] Перезапуск backend не сбрасывает документы/проекты — **документы (чтение) уже не сбрасываются** (реальный rag_service), но upload/patch документа и весь домен «Проекты» — по-прежнему in-memory, сбрасываются
- [ ] Загруженный в «Мою базу знаний» файл реально проходит ingestion-пайплайн rag_service (не таймер на 2.6с)
- [ ] `toggleTask`/`addFile` в проекте переживают reload страницы
- [ ] Чат проекта (`✦ Чат проекта` в `ProjectsPage.jsx`) открывает реальный `GROUP`-чат мессенджера, не заглушку `onOpenMessenger`

## Открытые вопросы (нужно решить, не молчать и не гадать перед стартом реализации)

1. Личные файлы в «Базе знаний» — идут через полный ingestion-пайплайн rag_service (webhook, Celery) или
   нужен упрощённый синхронный путь для маленьких файлов? Полный пайплайн даёт единообразие, синхронный —
   быстрее для UX загрузки.
2. Файлы проекта, которые НЕ предназначены для RAG-поиска (просто вложения) — где физически хранятся?
   Нужен ли backend'у собственный MinIO-клиент, или всё проходит через rag_service как единственного
   держателя S3 (второе — чище архитектурно, но добавляет rag_service ответственность не про RAG).