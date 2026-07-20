# Проекты + База знаний — детальный референс

Сводка фичи и живой чеклист — в `TODO.md` (Фича 5). Этот файл — то, чего нет в `TODO.md`:
полная схема таблиц, слои, и нерешённые вопросы.

## Проекты — модель предметной области

Новая схема Postgres `projects_schema` (по аналогии с `users_shema`):

| Таблица | Поля | Примечание |
|---|---|---|
| `projects` | `id`, `guid`, `name`, `desc`, `status`(enum: planning/active/review), `deadline`, `chat_id`, `created_by_id`, timestamps | `chat_id` — FK на `chats.id` (общий чат — надстройка над мессенджером), чат создаётся как `ChatType.GROUP` при создании проекта |
| `project_members` | `project_id`, `user_id`, `role`(text) | M2M, как `chat_participant` |
| `project_tasks` | `id`, `project_id`, `title`, `done`, `assignee_id`, `position` | `position` для сортировки в списке |
| `project_files` | `id`, `project_id`, `rag_doc_id`(nullable UUID), `filename`, `size_bytes`, `uploaded_by_id`, `created_at` | Если файл проиндексирован в rag_service — `rag_doc_id` заполнен и файл ищется через RAG с фильтром по `doc_id`; если это просто вложение — `rag_doc_id IS NULL`, хранится в бакете `projects` напрямую |
| `project_activity` | `id`, `project_id`, `actor_id`, `text`, `created_at` | Лог событий, генерируется сервисом при task/file/member-мутациях, не отдельный API |

## Слои

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

- `UnitOfWork` получает свойство `projects -> ProjectRepository`
- `dependencies.py` получает `get_project_service` + `ProjectServiceDep`, по образцу `get_chat_service`
- Создание проекта → в одной транзакции: `INSERT project` + `INSERT chats(chat_type=GROUP)` +
  `INSERT project_members` для создателя. Единственное место, где домен «Проекты» напрямую трогает
  домен «Чаты» — через `uow.chats` и `uow.projects` в одном `UnitOfWork`, не через HTTP.
- Загрузка файла в проект (`addFile` в `useProjects.js`) → `ProjectService` решает: если файл должен
  попасть в RAG — вызывает `RagClient.upload_document`, сохраняет `rag_doc_id`; иначе кладёт в
  MinIO-бакет `projects/{project_id}/...` напрямую (нужен свой S3-клиент в backend либо ещё один
  тонкий endpoint в rag_service `POST /storage/projects/{id}/files` — решить на этапе реализации).

## База знаний — proxy-слой

Документы — домен `rag_service` (`domain/document.py`, `application/document_service.py`), с
собственной DDD-структурой и таблицами Postgres. Заводить вторую копию в backend — дублирование
домена. `backend/api/knowledge_routes.py` — тонкий proxy к `rag_service`, по образцу `LLMClient`
(`backend/services/ai/llm_client.py`) — httpx-клиент по `service_url` из настроек.

```
backend/
  services/rag/
    rag_client.py          # httpx-клиент к rag_service, аналог LLMClient
  api/
    knowledge_routes.py    # заменяет knowledge_router из stub_routes.py
```

- `RagClient.list_documents(category, owner_user_id) -> list[DocumentSummary]`
- `RagClient.upload_document(file, owner_user_id) -> DocumentSummary`
- `RagClient.get_document(doc_id) -> DocumentDetail` (с `sections`, когда A10 в `rag_service/ISSUES.md` будет готов)

Фронт (`useKnowledgeBase.js`) не меняется — контракт `ENDPOINTS.KNOWLEDGE_DOCUMENTS` тот же, меняется
только бэкенд за ним.

## Открытые вопросы (нужно решить перед стартом реализации, не молчать и не гадать)

1. Личные файлы в «Базе знаний» — идут через полный ingestion-пайплайн rag_service (webhook, Celery)
   или нужен упрощённый синхронный путь для маленьких файлов? Полный пайплайн даёт единообразие,
   синхронный — быстрее для UX загрузки.
2. Файлы проекта, которые НЕ предназначены для RAG-поиска (просто вложения) — где физически хранятся?
   Нужен ли backend'у собственный MinIO-клиент, или всё проходит через rag_service как единственного
   держателя S3 (второе — чище архитектурно, но добавляет rag_service ответственность не про RAG).