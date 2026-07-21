# RAGProgramm — TODO

## Где искать баги и технический долг (по сервисам)

Этот файл — единый список **фич и планов** по всему проекту (ниже). Баги/архитектурный долг —
раздельно по сервисам, в файлах ниже. Эти файлы меняются быстрее, чем успевает синхронизироваться
что-либо ещё — при работе с конкретным багом сначала читать актуальный файл, не полагаться на
описание в этой таблице дальше факта "смотри туда".

| Сервис | Файл | Что внутри |
|---|---|---|
| rag_service | `rag_service/ISSUES.md` | Баги (B-серия), архитектурный долг (A-серия), типы/стиль (T-серия), мёртвый код (D-серия) |
| rag_service | `rag_service/PARSING_TABLES_PLAN.md` | Живой остаток по парсингу/таблицам (LLM-саммари по таблицам не сделано) — сжат 2026-07-20, историческое обоснование выбора Docling убрано, живо только в git-истории |
| llm_service | `llm_service/TODO.md` | Статус ML-роутера, LangGraph-агента, оставшиеся баги/долг |
| backend | `backend/MESSENGER_TODO.md` | Только ручные шаги проверки (Postman/браузер) — сжат 2026-07-20, чеклист сборки был полностью done, унесён в git-историю |
| backend | `backend/DDD_PLAN_knowledge_projects.md` | Детальная схема таблиц Проектов, слои, открытые вопросы — сама фича сведена в Фичу 5 ниже, этот файл только для деталей реализации |
| frontend | `frontend/TODO_HANDOFF.md` | Один незакрытый пункт (кнопка «Спросить ассистента» в читалке) — сжат 2026-07-20, остальное было done |

---

## Приоритетный план (аудит 2026-07-17)

Порядок — по риску/зависимостям, не по номеру.

### Фаза 0 — Security ✅ сделано 2026-07-20
- [x] Хешировать пароли в `UserService` при создании/смене админом (`backend/services/user_service.py`, `dependencies.py`) — `UserService` теперь получает `auth_handler`, хеширует в `create_user_repo`/`update_user_credentials`
- [x] Guard от самоудаления (`DELETE /admin/users/repo/{id}`) — `SelfActionForbiddenError` (400)
- [x] Guard от самопонижения/понижения последнего админа (`PATCH .../role`) — `SelfActionForbiddenError`/`LastAdminError` (400), `UserRepository.count_superusers()`

### Фаза 1 — Баги, ломающие пайплайн ✅ сделано 2026-07-20
- [x] Таблицы не долетают до ответов ассистента ✅ 2026-07-20 — `retrieve_service.py` теперь резолвит `[→ Таблица N]` в Markdown-таблицу (тот же маркер, что и читалка), собирает CSV одним батчем на все items
- [x] Ретрай-политика `DBAPIError` в `ingestion_service.py` ✅ 2026-07-20 — сужена до `OperationalError` (см. B5 в ISSUES.md, перенесён в исправленные)
- [x] Webhook double-dispatch race ✅ 2026-07-20 — per-record try/except в `handle_webhook` + идемпотентность в `TaskDispatcherService.dispatch_ingestion` (см. B6 в ISSUES.md, перенесён в исправленные)
- [x] `route_node` блокирует event loop ✅ 2026-07-20 — `.route()` теперь через `asyncio.to_thread` в `lean_rag_agent.py`
- [x] N+1 в списке Базы знаний ✅ 2026-07-20 — убран целиком, не просто ограничен: список (`GET /documents`) теперь без деталей, главы грузятся лениво только при открытии документа (новый `GET /api/knowledge/documents/{doc_id}`, `useKnowledgeBase.js::openDoc`)

### Фаза 2 — Достроить то, что фронт уже показывает как готовое
- [ ] Админ-панель: health-поллинг, источник Celery-задач (уже поднят `rag_flower`, просто не опрашивается), реальные `scope`/`ownerId` документов, персист rename/role/block, confirm-диалоги
- [ ] База знаний: upload/patch документа — снять с in-memory `_DOCUMENTS` в `stub_routes.py`
- [x] Заметки — бэкенд ✅ 2026-07-20, см. Фичу «Заметки» ниже. Фронт (`useNotes.js`) всё ещё на моках — не подключён к реальным эндпоинтам, это следующий шаг
- [ ] Проекты — полный DDD-бэкенд (см. Фичу 5 ниже) — `toggleTask`/`addFile` сейчас не переживают reload
- [ ] Задачи на день — новый домен, бэкенда нет вообще (см. Фичу 6 ниже); зависит от Проектов (дедлайны) и Заметок (напоминания) для «авто»-задач
- [ ] Главная (дашборд) — агрегатор Уведомлений/Напоминаний/Моих задач; сейчас фронт полностью на моках (`useHomeDashboard.js`), реальный смысл появится только после Заметок/Проектов/Задач/Мессенджера
- [ ] Мессенджер — фронтенд-хвосты: `MessengerPage.jsx`, `MessengerMessage.jsx`, `TypingIndicator.jsx`, роутинг в `App.jsx` (бэкенд полностью готов, см. `backend/MESSENGER_TODO.md`)

### Фаза 3 — Архитектурный долг
Полный список — `rag_service/ISSUES.md` (A1/A6/A7/A8/A9/A11, A10 миграции/`document_meta_sections`/саммари глав и таблиц, мёртвый код D1/D4/D6/D7/D8, дубль `MLQueryRouter` в llm_service).

### Фаза 4 — Новые фичи
См. «Фичи и планы» ниже — Фича 1 (AI-аудит), Фича 2 (автосаммари, нужен только триггер), Фича 4 (`@gpt` в мессенджере — можно брать сразу, зависимость снята), Фича 5 (= Фаза 2 «Проекты»).

### Фаза 5 — Готовность к релизу
Тесты, merge `mvp → main`, Grafana/Loki логи, остатки settings/dead-code — см. таблицу ниже пп. 9-15.

---

## Фичи и планы (весь проект, единым списком)

### Фича 1 — AI-аудит опросников по ГОСТам (Batch RAG) 📋 спецификация, не начато

**Бизнес-цель**: автоматический технический аудит опросных листов/ТЗ (до 100+ страниц) на
соответствие нормативке (ГОСТ/СП/ПУЭ/ПБ) из Qdrant. KPI из спеки — 4 часа ручной проверки → секунды,
−80% токенов относительно закидывания всего документа в контекст на каждом шаге.

**Архитектура — 3 шага** (юзер прислал развёрнутую спеку 2026-07-20, адаптирована под то, что уже
есть в коде — не копирую готовые классы из спеки один в один, см. отличия ниже):

```
Опросный лист (PDF/DOCX)
  → Step 1: Global Context Extractor (1 запрос к LLM) — вытащить упомянутые ГОСТ/СП/ПУЭ, категорию объекта
  → Step 2: Chapter Splitter — разбить на главы
  → по каждой главе параллельно (asyncio.gather):
      генерация поисковых запросов (LLM) → батч-поиск в Qdrant → сверка главы с найденными нормами (LLM)
  → Step 3: Report Aggregator — сплющить нарушения по всем главам в один отчёт
```

**Чем отличается от присланной спеки:**
- Батч-поиск в Qdrant **уже есть и уже быстрее** того, что в спеке — `RetrieveService.batch_search`/
  `QdrantVectorStorage.batch_search` (`query_batch_points`, один сетевой вызов на все запросы). Спека
  делает `asyncio.gather` по отдельному запросу на каждый — не реюзать, это шаг назад.
- `self.llm.agenerate_structured(prompt, response_model=PydanticModel)` из спеки **не существует**.
  `LLMProvider` (`OpenAICompatLLMProvider`/`GroqLLMProvider` в `llm_service/LLM_provider.py`) сейчас
  везде возвращает голый `str` — нет форсированного JSON/Pydantic-structured вывода вообще нигде в
  проекте. Это реальная новая инфраструктура, которую придётся строить (JSON mode у OpenAI-совместимого
  провайдера, или `instructor`-подобная обёртка с ретраем на невалидный JSON), не готовый кубик.
- Где физически живёт оркестрация 3 шагов — не решено. Батч-поиск/Qdrant — это `rag_service` (владеет
  Qdrant по архитектурному соглашению из `CLAUDE.md`), но LLM-вызовы — обычно `llm_service`. Разбить
  ли пайплайн между сервисами (rag_service отдаёт `POST /audit/batch-search`, llm_service дирижирует)
  или сделать единой цепочкой в одном сервисе — открытый вопрос, решать при старте реализации.

**Pydantic-схемы и системные промпты из спеки — годятся как есть**, полезный конкретный референс:
`GlobalScope`/`Chapter`/`QdrantQuery`/`AuditIssue`/`AuditReport`, промпт генерации поисковых запросов
и промпт сверки с правилами `MATCH`/`VIOLATION`/`WARNING`/`NOT_FOUND` — не переписывал, они не зависят
от того, чего в коде ещё нет.

**Что нужно:**
- [ ] Structured-output слой в llm_service (Pydantic response_model из LLM-ответа) — блокирует весь Step 1/2а/2в
- [ ] Парсер опросного листа (PDF/DOCX → главы) — можно переиспользовать Docling-пайплайн rag_service или отдельный upload-путь, не смешивая с индексацией документов в общую Базу знаний
- [ ] Эндпоинт(ы) для пайплайна — решить владение (см. открытый вопрос выше)
- [ ] Поле `category` в payload при индексации ГОСТов (UI в admin-panel) — фильтрация нерелевантных норм при батч-поиске
- [ ] Системные промпты (Step 1 extract-scope, Step 2а generate-queries, Step 2б audit-compare) — черновики есть в спеке, доработать под реальную структуру ГОСТов в базе
- [ ] Ответ: `AuditReport` JSON → таблица на фронте с фильтрацией по статусам

---

### Фича 2 — Автосаммари по счётчику ✳️ частично готово
`POST /llm/summary` уже есть. Осталось подключить триггер.

- [ ] Колонка `messages_count` в таблице `chats` (или считать при записи)
- [ ] При записи 20-го сообщения — вызов `generate_chat_summary.delay(chat_id)` через Celery
- [ ] Celery-задача обновляет поле `summary` в БД

---

### Фича 3 — Корпоративный мессенджер (WebSockets) ✅ бэкенд готов
Личные чаты между сотрудниками с AI как участником. Бэкенд полностью реализован
(`backend/MESSENGER_TODO.md`, блоки 1–10, 8К, 8Л) — таблицы/`ConnectionManager`/WS-эндпоинт/
`useMessengerSocket.js` на фронте уже есть.

**Что реально осталось** (см. Фаза 2 в приоритетном плане выше):
- [ ] `frontend/src/pages/MessengerPage.jsx`, `MessengerMessage.jsx`, `TypingIndicator.jsx`
- [ ] Роутинг `MessengerPage` в `App.jsx`
- [ ] Push-уведомления офлайн-получателю через Celery (`send_push_notification.delay`) — не реализовано; когда возьмём Фичу 7 (Web Push ниже), это тот же механизм, не отдельный

---

### Фича 4 — AI как участник чата
Бот с фиксированным `user_id` в Postgres, отвечает по тегу `@gpt`.

- При обнаружении `@gpt` → `process_ai_respond.delay(chat_id, text)` в Celery
- Celery: поиск в Qdrant → LLM → запись ответа от `sender_id=UUID_БОТА` → `manager.send_layout_message()`
- Пользователь видит ответ бота в чате без перезагрузки

**Зависела от Фичи 3 — та уже готова на бэкенде, можно брать сразу.**

---

### Фича 5 — База знаний (проксирование) + Управление проектами

Полная детализация и открытые вопросы — `backend/DDD_PLAN_knowledge_projects.md`. Здесь — сведённая суть.

**База знаний — что доделать в rag_service, не в backend** (backend остаётся тонким proxy):
- [ ] `category: str | None` на `documents` (нужно и для Фичи 1)
- [ ] `owner_user_id` на `documents` — для личных документов
- [ ] `summary`/`sections[]` по главам — упирается в A10 (`rag_service/ISSUES.md`)
- [ ] Выделить `RagClient`/`backend/api/knowledge_routes.py` из `stub_routes.py` (`knowledge_router`)

**Проекты — новый домен, backend владеет им целиком** (по образцу Chats: models → repository →
service через `UnitOfWork` → routes), сейчас `_PROJECTS` в `stub_routes.py` — hardcoded заглушка:
- [ ] Схема `projects_schema`: `projects` (name/desc/status/deadline/chat_id/created_by_id),
      `project_members` (M2M), `project_tasks` (title/done/assignee/position),
      `project_files` (rag_doc_id nullable — либо реальный RAG-документ, либо просто вложение в
      бакете `projects`), `project_activity` (лог событий)
- [ ] Создание проекта — одна транзакция: `INSERT project` + `INSERT chats(chat_type=GROUP)` +
      `INSERT project_members` для создателя (через `uow.chats`+`uow.projects` в одном `UnitOfWork`)
- [ ] `toggleTask`/`addFile` в `useProjects.js` — переключить с локального `setState` на реальные `PATCH`/`POST`
- [ ] Чат проекта (`✦ Чат проекта` в `ProjectsPage.jsx`) — открывать реальный `GROUP`-чат, не заглушку

**Открытые вопросы** (см. `DDD_PLAN_knowledge_projects.md` — не решены):
- [ ] Личные файлы в Базе знаний — полный ingestion-пайплайн (webhook+Celery) или упрощённый синхронный путь для мелких файлов?
- [ ] Файлы проекта не для RAG (просто вложения) — нужен ли backend свой S3-клиент, или всё через rag_service?

**Порядок работ:** 1) `category`/`owner_user_id` в rag_service → 2) `RagClient`+`knowledge_routes.py`
в backend → 3) миграция `projects_schema` → 4) `ProjectRepository`→`ProjectService`→`project_routes.py`
→ 5) удалить `stub_routes.py` целиком.

---

### Заметки ✅ бэкенд готов 2026-07-20, фронт ещё не переключён

Владение разделено: **backend** хранит таблицу `notes` (`users_shema.notes`, реальный FK на
`users`, миграция `migrations/users/versions/a1c3e7f92b40_003_add_notes_table.py`) и отдаёт полный
CRUD (`backend/api/notes_routes.py`, `/api/notes/*`). **rag_service** только векторизует — не знает
про title/tags/folder, получает `{note_id, user_id, text}` и чанкует/эмбеддит/апсертит в отдельную
Qdrant-коллекцию `notes_collection_with_sparse_vector` (`rag_service/application/note_vectorization_service.py`).

Поток индексации: `POST /api/notes/{guid}/index` (backend, status→`indexing`) → `POST /notes/{guid}/index`
(rag_service, синхронно ставит Celery-таску `index_note`) → таска чанкует+эмбеддит+апсертит → **колбэк**
`POST /internal/notes/{guid}/index-complete` в backend (без авторизации, доверие к внутренней docker-сети,
как у MinIO-вебхука) → backend проставляет `status`/`chunk_count`.

Попутный рефакторинг (нужен был для двух Qdrant-коллекций без двух клиентов): `QdrantVectorStorage`
принимает готовый `AsyncQdrantClient` вместо того чтобы создавать свой — один клиент на весь `rag_service`,
`collection` остаётся привязан к инстансу (как раньше). `delete_points(doc_id)` обобщён до
`delete_by_field(field, value)` — теперь и документы, и заметки удаляют точки одним методом.

**Не сделано:**
- [ ] Фронт `hooks/useNotes.js` — переключить с моков на реальные `/api/notes/*` (сейчас это отдельный шаг, ещё не начат)
- [ ] Реальный LLM-вызов вместо мока `transformRawText` (мок оставлен сознательно)
- [ ] Поиск по заметкам (`POST /notes/search` в rag_service) — пока не нужен, ничего его не вызывает
- [ ] Alembic-миграция не прогонялась на реальной БД (Docker не был поднят в сессии) — при первом запуске стоит проверить `alembic -n users upgrade head`
- [ ] Колонка `Notes.reminder` — временная. Как только берём Фичу 7 (ниже), заменится отдельной таблицей `reminders`; новую миграцию на дроп колонки делать в связке с Фичей 7, не раньше

---

### Фича 6 — Задачи на день + Главная (дашборд) ✳️ фронт готов (2026-07-20), бэкенда нет
Два новых экрана внедрены на фронте (мок), см. `frontend/handoff_3_экрана/ГЛАВНАЯ И ЗАДАЧИ - внедрение.md`,
`hooks/useTasks.js`, `hooks/useHomeDashboard.js`. Порядок бэкенда — по зависимостям (см. ниже), не с нуля.

**Задачи на день:**
- [ ] Таблица `tasks` (id, user_id, day date, title, priority enum high/med/low, manual bool, done bool, source_type enum project/note nullable, source_id nullable)
- [ ] `GET /api/tasks?week_start=` / `POST /api/tasks` / `PATCH /api/tasks/{id}` (toggle/edit) / `DELETE /api/tasks/{id}`
- [ ] `POST /api/tasks/ai-parse` — реальный вызов LLM (парсинг {title, day, priority} из свободного текста, промпт уже есть в файле внедрения §2), сейчас на фронте regex-мок `parseAiTask` в `useTasks.js`
- [ ] Перенос невыполненных на завтра — **решить**: считать на лету в `GET` (как сейчас делает фронт в `useTasks.js`, без мутации и без Celery-джобы — проще) или отдельная полночная Celery-джоба, которая физически переставляет `day`. Первое проще и, скорее всего, достаточно.
- [ ] «Авто»-задачи из проектов (по дедлайну) и заметок (по напоминанию) — **зависит от Фичи 5/Заметок выше**, до них это просто ручные задачи без источника

**Главная (дашборд):**
- [ ] Один агрегирующий `GET /api/dashboard` (или 3 параллельных вызова) — Notifications/Reminders/MyTasks/SearchResults, типы описаны в файле внедрения §1
- [ ] Источник Notifications — по сути лента активности (упоминания в чатах/мессенджере, новые документы, статус индексации); нет отдельного домена, надо решить, откуда её строить (event log? отдельная таблица?)
- [ ] Глобальный поиск — либо единый индекс по чатам/докам/заметкам/проектам, либо 3 параллельных запроса
- [ ] Реального смысла эти два эндпоинта не будет, пока не готовы Заметки/Проекты/Задачи — Главная агрегирует их данные

**Рекомендуемый порядок бэкенда** (зависимость определяет порядок, не наоборот):
1. Заметки (готово) → 2. Проекты (Фича 5) → 3. Задачи на день → 4. Главная (агрегатор поверх 1+2+3+Мессенджера)

---

### Фича 7 — Отложенные Web Push уведомления (RabbitMQ Delayed Exchange + VAPID) 📋 спецификация, не начато

Точные пуш-уведомления (напоминания из заметок/задач) при закрытом браузере, без периодического опроса
БД на предмет "чего там уже наступило". Юзер прислал развёрнутую Spec-2 (2026-07-20) — архитектура
адаптирована под реальную схему проекта (см. решения ниже), не взята буквально.

**Ключевые решения сессии (отличаются от Spec-2 как прислано):**
- **Брокер**: новый **RabbitMQ рядом с Redis**, не вместо. `rag_service`/`rag_worker`/`rag_flower` продолжают
  сидеть на Redis как есть — не трогаем уже рабочий пайплайн индексации документов. RabbitMQ заводится
  сначала только под `backend_worker` (пуши); если приживётся — можно позже переносить на него другие
  задачи `backend`, но это отдельное решение потом, не сейчас.
- **Индексация заметок НЕ переезжает на прямую публикацию в очередь** — оставляем уже сделанный и
  проверенный путь `backend` → HTTP `POST /notes/{id}/index` → `rag_service` сам ставит Celery-таску
  (см. Фичу «Заметки» выше). В Spec-2 индексация шла через `celery_app.send_task(...,queue="rag_queue")`
  напрямую из backend — это более тесная связанность (backend знает имя таски/очередь чужого сервиса),
  переделывать уже рабочее ради этого не стали.
- **Напоминания — отдельная таблица `reminders`** (title/body/status свои, `note_id` опциональный FK),
  не поле на `Notes` — совместимо с напоминаниями вне контекста заметки (Задачи на день/Главная, Фича 6).
- **id — по конвенции проекта** (int PK + `guid` UUID, как `Users`/`Chats`/`Notes`), не `UUID PRIMARY KEY`
  как в присланном SQL — тот не встанет на текущую схему (`Users.id` уже `int`, не UUID).

**Компоненты:**
- `docker-compose`: контейнер `rabbitmq` (образ с delayed-message-exchange плагином, напр.
  `heiducks/rabbitmq-delayed-message-exchange`), новый сервис `backend_worker` (Celery, слушает свою
  очередь, **без ML-зависимостей** — только `pywebpush`+лёгкие таски)
- `backend`: своя первая Celery-настройка (`celery_app.py` в backend — сейчас там Celery вообще нет,
  все асинхронные задачи идут через HTTP в `rag_service`), таблицы `reminders` + `user_push_subscriptions`
  (миграция поверх уже сделанной для `Notes`)
- `backend`: эндпоинт сохранения push-подписки браузера (`endpoint`/`p256dh`/`auth` от `PushManager.subscribe()`)
- `backend`: при создании напоминания с `due_datetime` — `celery_app.send_task(..., queue="backend_queue", headers={"x-delay": delay_ms})`
- `backend_worker`: по срабатыванию — читает `push_subscription` пользователя, `pywebpush()`
- `frontend`: генерация/хранение VAPID public key, `sw.js` (Service Worker) — запрос permission,
  подписка на `PushManager`, обработка `push`-события → нативное уведомление ОС, клик → открыть заметку

**Открытые вопросы (не решены, решать при старте реализации):**
- [ ] Генерация и хранение VAPID-ключей (где, как ротировать)
- [ ] `sw.js` — регистрация в `frontend/public/`, интеграция с текущим `AppRail`/роутингом (deep link на заметку по клику)
- [ ] UI запроса permission на уведомления (когда показывать, как не быть навязчивым)
- [ ] Reminders создаются откуда: только из Заметок, или сразу общий механизм для Задач на день (Фича 6) тоже?

---

## MVP: задачи до релиза

| # | Задача | Сервис | Приоритет | Статус |
|---|---|---|---|---|
| 1 | Один `.env` файл — убрать сервисные env, один корневой | все | Высокий | ✅ Готово |
| 2 | Логи — убрать `print()`, настроить structured JSON logging | все | Высокий | ✅ Готово |
| 3 | Ошибки — кастомные исключения (ChatNotFoundError, LLMError, LLMUnavailableError), убрать HTTPException из сервисов | llm, backend | Высокий | ✅ Готово |
| 4 | Summary — ConversationService, count_after по БД, POST /llm/summary, generate_summary() | backend, llm | Высокий | ✅ Готово |
| 5 | Роли (user/admin) — `is_superuser` как источник правды, гейтинг `/admin/*`, `PATCH .../role` | backend, frontend | Средний | ✅ Готово |
| 6 | Профиль пользователя — расширить модель (имя, роль, аватар, дата) | backend, frontend | Средний | ⬜ Не начато |
| 7 | `GET /health` для llm_service | llm | Средний | ✅ Готово |
| 8 | Переименовать `history_massage` → `history_messages` | llm, backend | Низкий | ✅ Готово |
| 9 | Убрать мёртвый код — `agent_service.py`, `answer_service.py`, старый `context_builder.py`, `promt/promts.py` | llm | Низкий | ⬜ Не начато |
| 10 | Вынести параметры в settings — `top_k`, `chunk_size`, `max_context_chars` | rag, llm | Низкий | ⬜ Не начато |
| 11 | PDF склейка — `_fix_merged_prepositions` в `TextCleaner` | rag | Низкий | ⬜ Не начато |
| 12 | Structured logging во всех сервисах (backend, llm_service) | backend, llm | Средний | ⬜ Не начато |
| 13 | Тесты — покрыть retrieve, ingestion, chat, LLM pipeline | все | Средний | ⬜ Не начато |
| 14 | Merge `mvp` → `main` | — | — | ⬜ Не начато |
| 15 | Grafana — логи не доходят (Loki driver настроен в docker-compose, но записи не поступают) | все | Средний | ⬜ Не начато |
| 16 | `GET /documents/{doc_id}/chapters/{n}` — текст главы + таблицы (для читалки) | rag, backend, frontend | Средний | ✅ Готово |

---

## Учётки

- Первый (и пока единственный) админ: логин `admin`, пароль `admin1234` (заведён вручную через `/auth/register` + `is_superuser=true` напрямую в БД — самостоятельная регистрация не даёт роль admin, только следующих админов может назначать уже существующий админ через вкладку «Пользователи» в админ-панели). Учётка dev-стенда, для прод-окружения пароль сменить.

---

## Гибридный поиск — статус

- [x] BM25 через серверный `qdrant/bm25` (`Document(text, model)`)
- [x] Формат точек: `dense_vector` + `bm25_sparse_vector`
- [x] Коллекция: `vectors_config` + `sparse_vectors_config` (IDF modifier)
- [x] Пакетный поиск через `query_batch_points`
- [x] Prefetch + DBSF fusion
- [ ] Очистка текста перед индексацией (склеенные слова)
- [ ] Score threshold после DBSF — подобрать порог
- [ ] Полная переиндексация на новую схему коллекции
- [ ] Стресс-тест на аббревиатурах и склеенных словах