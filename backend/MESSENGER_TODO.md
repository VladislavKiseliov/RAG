# Чеклист запуска мессенджера

Референс: https://github.com/notarious2/fastapi-chat

---

## БЛОК 1 — `services/websocket_handlers.py` ✅
- [x] Убраны декораторы и глобальный `socket_manager`. Хендлеры принимают `socket_manager` как аргумент. Добавлена `register_handlers(socket_manager)`, вызывается в `lifespan` из `main.py`

---

## БЛОК 2 — `services/auth_service.py` ✅
- [x] `CurrentUser` расширен: `id: int`, `guid: uuid.UUID`, `first_name: str | None`, `last_name: str | None`
- [x] `get_user_from_token` — поиск по `guid` через `get_user_by_guid`, заполняет все поля
- [x] Auth bug исправлен: `login` теперь кладёт `str(user.guid)` в JWT `sub`
- [x] Добавлены пропущенные `commit()` в `login`, `refresh`, `logout`, `register`

---

## БЛОК 3 — `repository/chat_repository.py` ✅
- [x] `ChatRepository.get_user_active_chats` — JOIN через `chat_participant`, фильтр по `user_id: int`
- [x] `ChatService.get_user_active_chats` — передаёт `current_user.id` (int)

---

## БЛОК 4 — `schemas/websocket_schemas.py` ✅
- [x] `is_new: bool = False` добавлен в `SendMessageSchema`

---

## БЛОК 5 — `dependencies.py` ✅
- [x] `get_message_service()` и `MessageServiceDep` добавлены

---

## БЛОК 6 — `api/websocket_router.py` ✅
- [x] Убраны: `cache`, `db_session`, `user_status_task`, `mark_user_as_offline`
- [x] `message_service: MessageServiceDep` передаётся в dispatch

---

## БЛОК 7 — `main.py` ✅
- [x] `websocket_router` зарегистрирован

---

## БЛОК 8 — Унификация модели + HTTP роуты мессенджера

> Всё в одной модели: `Chats` (chat_type) + `chat_participant` + `Messages`.

---

### 8А — Модель `Messages`: поле `role` ✅
- [x] `role: Mapped[str | None]` добавлен в `Messages`

---

### 8Б — `ChatRepository` ✅
- [x] `create_chat` — `Chats(chat_type=..., created_by_id=user_id, title=title)` без несуществующих полей
- [x] `get_user_active_chats` — JOIN через `chat_participant`, опциональный фильтр `chat_type`
- [x] `get_chat(chat_id: int)` — по integer PK
- [x] `delete_chat(chat_id: int)` — по integer PK
- [x] `update_chat_title(chat_id: int, new_title: str)` — по integer PK
- [x] `get_chat_member_guids` — исправлен баг `.c.chat_id`
- [x] `get_chat_by_guid(chat_guid: UUID)` — новый метод для ConversationService
- [x] `get_chat_id_by_guid(chat_guid: UUID) -> int` — новый метод

---

### 8В — `MessageRepository` ✅
- [x] `add_message` — объединён с `create_messenger_message`, `role`/`user_id`/`sources` опциональны
- [x] `get_history(chat_id: int)` — тип исправлен
- [x] `get_recent(chat_id: int)` — тип исправлен
- [x] `count_after(chat_id: int, after_id: int | None)` — типы исправлены
- [x] `get_messages_after(chat_id: int, after_id: int | None)` — типы исправлены
- [x] `get_messages_paginated(chat_id: int, limit, offset)` — новый метод для мессенджера

---

### 8Г — `ChatService` и `ConversationService` ✅
- [x] `ChatService` — полная перезапись на UnitOfWork, `user_id: int`, `await uow.commit()` везде
- [x] `ConversationService` — импорты исправлены, везде `chat_guid → get_chat_by_guid → chat.id (int)`

---

### 8Д — `UnitOfWork` ✅
- [x] `messenger` property добавлен → `MessengerRepository`
- [x] Импорты исправлены: каждый репозиторий из своего модуля

---

### 8Е — Новые методы репозитория для мессенджера ✅
- [x] `ChatRepository.create_direct_chat(creator_id, friend_id)` — chat + 2 записи в `chat_participant`
- [x] `ChatRepository.get_user_chats_with_details(user_id)` — один SQL: чат + друг + последнее сообщение
- [x] `ChatRepository.is_chat_participant(chat_id, user_id)` — проверка доступа
- [x] `MessageRepository.get_messages_paginated(chat_id, limit, offset)`

---

### 8Ж — `MessengerService` ✅
- [x] `create_direct_chat(user_id, friend_guid)` — находит друга, создаёт чат, возвращает dict
- [x] `get_user_chats(user_id)` — список чатов с деталями
- [x] `get_chat_messages(chat_guid, user_id, limit, offset)` — история с проверкой доступа

---

### 8З — HTTP роуты и регистрация ✅
- [x] Создан `api/messenger_routes.py` — 3 эндпоинта
- [x] `MessengerServiceDep` добавлен в `dependencies.py`
- [x] `app.include_router(messenger_router)` в `main.py`
- [x] `websocket_utils.py` адаптирован под dict из `MessengerService`

---

### 8И — AI-чаты: синхронизация роутов и безопасность ✅
- [x] `chats_routes.py` синхронизирован с новым `ChatService` (guid вместо uuid везде)
- [x] Проверка доступа к чату через `_resolve_chat_for_user` внутри сервиса — один JOIN-запрос
- [x] `ChatRepository.get_chat_id_for_participant` — резолвит guid в id + проверяет участие
- [x] Логика "найди → проверь → выполни" убрана из роутов, живёт только в сервисе

---

## БЛОК 8К — Реорганизация файлов бэкенда ✅

- [x] `services/ai/llm_client.py` — перемещён из `services/llm_client.py`
- [x] `services/ai/conversation_service.py` — перемещён из `services/ConversationService.py`
- [x] `services/messenger/websocket_manager.py` — перемещён из `services/websocket_manager.py`
- [x] `services/messenger/websocket_utils.py` — перемещён из `services/websocket_utils.py`
- [x] `services/messenger/websocket_handlers.py` — перемещён из `services/websocket_handlers.py`
- [x] `services/messenger/message_service.py` — перемещён из `services/MessageService.py`
- [x] `services/messenger/messenger_service.py` — перемещён из `services/messenger_service.py`
- [x] `repository/messenger_repository.py` — извлечён из `user_repository.py`
- [x] Старые файлы удалены, все импорты обновлены (`infrastructure.py`, `dependencies.py`, `main.py`, `unit_of_work.py`, `messenger_routes.py`)
- [x] Без `__init__.py` — namespace packages Python 3.3+

---

## БЛОК 8Л — Фиксы AI-чатов и поиск пользователей ✅

- [x] `ChatRepository.create_chat` — теперь добавляет создателя в `chat_participant` (без этого `get_history` не работал)
- [x] `ChatBaseSchema` — исправлены aliases: `chat_id = Field(validation_alias="id")`, `chat_guid = Field(validation_alias="guid")`; `title` стал Optional
- [x] `UserRepository.search_users(query, exclude_id)` — ilike по `first_name`, `last_name`, `login`; исключает текущего пользователя
- [x] `UserService.search_users(query, exclude_id)` — возвращает `guid`, `first_name`, `last_name`, `login`, `job_title`
- [x] `GET /api/users/search?q=` — новый endpoint в `profile_routes.py`

---

## БЛОК 9 — Фронтенд: WS клиент ✅

`frontend/src/hooks/useMessengerSocket.js`

- [x] Подключение к `ws://localhost:8000/websocket/ws/?token=<accessToken>`
- [x] Реконнект с exponential backoff
- [x] Dispatch по `type`: `new_message`, `message_read`, `user_typing`, `new_chat_created`, `chat_deleted`, `error`
- [x] `sendMessage(chat_guid, content)`
- [x] `sendTyping(chat_guid)`
- [x] `markRead(chat_guid, message_guid)`

---

## БЛОК 10 — Фронтенд: стейт мессенджера ✅

`frontend/src/hooks/useMessenger.js`

- [x] `chats`, `activeChatGuid`, `messages`, `typingUsers`
- [x] `loadChats()`, `loadMessages(chat_guid)`, `createDirectChat(friend_guid)`, `openChat(chat_guid)`
- [x] Обработчики WS событий (`handleWsMessage`)

---

## БЛОК 11 — Фронтенд: компоненты ⚠️ (частично)

- [x] `frontend/src/components/MessengerChatList.jsx` — список чатов с именем друга и последним сообщением
- [x] `frontend/src/components/UserPickerModal.jsx` — поиск пользователей с дебаунсом 300ms
- [ ] `frontend/src/pages/MessengerPage.jsx` — страница мессенджера (не создана)
- [ ] `frontend/src/components/MessengerMessage.jsx` — пузырь сообщения
- [ ] `frontend/src/components/TypingIndicator.jsx`

---

## БЛОК 12 — Фронтенд: навигация и интеграция ⚠️ (частично)

- [x] `Sidebar.jsx` — три секции (Мессенджер / Проекты / Чат с ИИ) с collapse/expand
- [x] `config/api.jsx` — ENDPOINTS мессенджера (`MESSENGER_CHATS`, `MESSENGER_DIRECT`, `MESSENGER_MESSAGES`, `MESSENGER_WS`)
- [x] `ChatPage.jsx` — интегрированы `useMessenger` и `useMessengerSocket`, переключение режимов
- [ ] Сборка `MessengerPage` и подключение в `App.jsx` / роутинг

---

## Что осталось

```
Фронтенд:
  11 → MessengerPage.jsx, MessengerMessage.jsx, TypingIndicator.jsx
  12 → App.jsx роутинг на MessengerPage

Проверка:
  Postman: POST /messenger/chats/direct, GET /messenger/chats/
  Postman: GET /api/users/search?q=иван
  Браузер: два окна — один пишет, второй получает по WS
```