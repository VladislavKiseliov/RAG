# RAGProgramm — TODO

## MVP: задачи до релиза

| # | Задача | Сервис | Приоритет | Статус |
|---|---|---|---|---|
| 1 | Один `.env` файл — убрать сервисные env, один корневой | все | Высокий | ✅ Готово |
| 2 | Логи — убрать `print()`, настроить structured JSON logging | все | Высокий | ✅ Готово |
| 3 | Ошибки — кастомные исключения (ChatNotFoundError, LLMError, LLMUnavailableError), убрать HTTPException из сервисов | llm, backend | Высокий | ✅ Готово |
| 4 | Summary — ConversationService, count_after по БД, POST /llm/summary, generate_summary() | backend, llm | Высокий | ✅ Готово |
| 5 | Регистрация — валидация, роли (user/admin) | backend | Средний | 🔄 Частично |
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

---

## Дальнейшие планы

### Фича 1 — AI-аудит документов (Batch RAG)
Проверка опросного листа / ТЗ на соответствие ГОСТам через пакетный поиск по Qdrant.

**Как работает:**
- Парсим опросный лист → получаем массив строк по разделам
- Один батч-запрос в Qdrant (`query_batch_points`) — все строки за один сетевой вызов
- В payload чанков ГОСТов кладём теги `{"category": "cables"}` → фильтрация при поиске исключает нерелевантные ГОСТы
- LLM получает промпт: слева пункты опросника, справа нормы из ГОСТов в том же порядке
- Возвращает таблицу несоответствий

**Что нужно:**
- [ ] Парсер опросного листа (PDF/DOCX → структурированные разделы)
- [ ] Эндпоинт `POST /audit/questionnaire` в rag_service или отдельный сервис
- [ ] Поле `category` в payload при индексации документов (UI в admin-panel)
- [ ] Промпт аудитора в llm_service
- [ ] Ответ: JSON с несоответствиями + источники из ГОСТов

---

### Фича 2 — Автосаммари по счётчику ✳️ частично готово
`POST /llm/summary` уже есть. Осталось подключить триггер.

- [ ] Колонка `messages_count` в таблице `chats` (или считать при записи)
- [ ] При записи 20-го сообщения — вызов `generate_chat_summary.delay(chat_id)` через Celery
- [ ] Celery-задача обновляет поле `summary` в БД

---

### Фича 3 — Корпоративный мессенджер (WebSockets)
Личные и групповые чаты между сотрудниками с AI как участником.

**Архитектура:**
- Загрузка истории: `GET /api/v1/chats/{id}/messages` (HTTP, последние 20 из Postgres)
- Реальное время: WebSocket `ws://.../chats/{id}/ws`, `ConnectionManager` хранит `active_connections[user_id]`
- Онлайн: сообщение через вебсокет мгновенно
- Офлайн: `send_push_notification.delay(recipient_id, text)` через Celery

**Что нужно:**
- [ ] Новые таблицы: `direct_chats`, `chat_members`, `messages`
- [ ] `ConnectionManager` — singleton, хранит WebSocket по `user_id`
- [ ] WebSocket эндпоинт в backend
- [ ] Push-уведомления (Celery задача)

---

### Фича 4 — AI как участник чата
Бот с фиксированным `user_id` в Postgres, отвечает по тегу `@gpt`.

- При обнаружении `@gpt` → `process_ai_respond.delay(chat_id, text)` в Celery
- Celery: поиск в Qdrant → LLM → запись ответа от `sender_id=UUID_БОТА` → `manager.send_layout_message()`
- Пользователь видит ответ бота в чате без перезагрузки

**Зависит от Фичи 3.**

---

### Фича 5 — Управление проектами
Группа проекта с общим чатом, хранилищем файлов и AI-ассистентом с контекстом проекта.
- Участники, роли, общий чат (надстройка над мессенджером)
- Хранилище: общий бакет `projects`, папка `{project_id}/...` на проект (см. схему из 3 доменных бакетов в `rag_service/ISSUES.md`, A10)
- RAG только по файлам проекта (`doc_id` фильтр)