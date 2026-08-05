# Backend — Issues & Fixes

Заведено 2026-08-03 по итогам агентского аудита безопасности/архитектуры всего проекта
(4 параллельных агента, по одному на сервис). Формат — как в `rag_service/ISSUES.md`:
🔴 Баги (B-серия), 🟠 Архитектурные проблемы (A-серия), не исправлено.

---

## 🔴 Баги

| # | Было | Файл | Строка |
|---|---|---|---|
| B3 | Non-timing-safe сравнение refresh-токена (`RefreshTokens.token == token` — обычное SQL-равенство) — в отличие от `notes_routes.py::index_complete`, где для internal-webhook токена уже применяется `hmac.compare_digest`. Теоретический тайминговый side-channel на refresh-токен; низкая практическая эксплуатируемость из-за сетевого джиттера и энтропии токена (48 байт), но это единственное место в auth, где устоявшийся в проекте паттерн `compare_digest` не применён | `repository/auth_repository.py` | 60–71 |

---

## ✅ Исправлено (2026-08-03)

| # | Было | Как исправлено |
|---|---|---|
| B1 | 🔴 **Критично.** `add_user_to_chat_handler` привязывал произвольный `chat_guid` к произвольному `chat_id` из клиентского WS-сообщения без какой-либо проверки в БД, а `MessageService.resolve_chat()` при разрешении чата сначала смотрел именно в этот in-memory кэш `chats` (per-connection), и только при промахе шёл в БД — притом кэш заполнялся `get_chat_id_by_guid` (тоже без проверки участия) даже без `add_user_to_chat`. Аутентифицированный пользователь мог подменить чужой `chat_id`/угадать чужой `chat_guid` и писать/читать в чужом чате, выдавая себя за легитимного участника | `resolve_chat()` теперь принимает `user_id` и резолвит через `get_chat_id_for_participant(chat_guid, user_id)` (участие проверяется в БД на каждый холодный резолв) — правка одной точки чинит `new_message`/`user_typing`/`mark_message_read` разом. `add_user_to_chat_handler` переписан: больше не пишет в кэш напрямую, зовёт тот же проверенный `resolve_chat`; клиентское поле `chat_id` убрано из `AddUserToChatSchema` целиком (фронт его и не использовал). Живой E2E-тест: свой чат — 200, чужой/несуществующий `chat_guid` — `ChatNotFoundError` |
| B2 | 🔴 **Критично.** `ConversationService.process_message`/`process_message_stream`/`ensure_chat_exists`/`get_context_chat` резолвили AI-чат через `ChatRepository.get_chat_by_guid(chat_guid)` без фильтра по `user_id` — в отличие от `get_chat_id_for_participant`, уже правильно используемого в `chat_service.py`/`messenger_service.py`. Пользователь A, зная/получив `chat_guid` чата пользователя B, дописывал сообщения в чужую историю без единой проверки принадлежности | Новый `ChatRepository.get_chat_by_guid_for_participant(chat_guid, user_id)` (join на `chat_participant`) — заменил `get_chat_by_guid` во всех 4 местах `ConversationService`. `ensure_chat_exists` теперь принимает `user_id`; `_validate_stream_chat_exists` (Depends в `chats_routes.py`) теперь берёт `current_user` и передаёт `current_user.id` — раньше не имел доступа к пользователю вообще. Живой тест на реальном стенде: свой чат → `200 {"response": "pong", ...}`, случайный `chat_guid` → `404 ChatNotFoundError`. `get_chat_by_guid` (без проверки участия) остался в `chat_repository.py` неиспользуемым — не удалён, публичный метод репозитория, вне скоупа этой правки |

---

## ✅ Исправлено (2026-08-05)

| # | Было | Как исправлено |
|---|---|---|
| B4 | 🔴 `MessageRepository.get_history(chat_id, limit=50)` — `GET /api/chats/{chat_guid}` (загрузка истории чата при открытии/перезагрузке страницы) — сортировал `ORDER BY Messages.id.asc() LIMIT 50`, то есть отдавал первые 50 сообщений (самые старые), а не последние 50. В любом чате длиннее 50 сообщений всё после 50-го — включая только что отправленные — никогда не попадало в ответ, хотя было в БД. Найдено по репорту пользователя: «сообщение есть в БД, но в чате его нет» после перезагрузки страницы. Подтверждено живьём на реальном чате (67 сообщений, id 264–452) — до фикса возвращались id 264–313, последние 17 не долетали | `order_by(Messages.id.desc())` + `.limit(limit)` + `rows.reverse()` — тот же паттерн, что уже был верно реализован в соседнем `get_recent()` в этом же файле. Проверено живьём на том же чате: последнее сообщение (id 452) теперь в выдаче |

---

## 🟠 Архитектурные / поведенческие проблемы

| # | Описание | Файл | Строка |
|---|---|---|---|
| A1 | Нет rate-limiting на `/auth/login` и `/auth/register` — `fastapi_limiter`/`pyrate_limiter` подключены только к websocket-эндпоинту. Неограниченный подбор пароля против `/auth/login`, неограниченное массовое создание фейковых аккаунтов через `/auth/register` | `api/auth_routes.py`, `main.py` | — |
| A2 | Per-request `httpx.AsyncClient` вместо переиспользуемого пула — каждый проксирующий admin/knowledge-base вызов открывает новое соединение с нуля. Под конкурентным поллингом админ-дашборда (`/admin/system/health` даёт 6 исходящих соединений на один вызов) — лишний churn соединений/задержка, под нагрузкой может исчерпать эфемерные порты. Уже фиксировалось в code-review punchlist 2026-07-21, не починено | `api/admin_routes.py` (`_proxy_request`, `_measure_http`), `api/chats_routes.py:97`, `api/stub_routes.py`, `services/note_service.py` | — |

---

## ✅ Проверено аудитом, проблем не найдено

SQL-инъекций нет (все репозитории — SQLAlchemy Core/ORM с bound-параметрами). Секретов в коде нет (всё через `pydantic-settings`). CORS — explicit origin allow-list, не wildcard. Внутренний вебхук (`notes_routes.py:89-98`) корректно проверяется `hmac.compare_digest`. Admin-роуты корректно гейтятся на уровне роутера (`Depends(require_admin_user)`, `admin_routes.py:16`) — ни одного роута без гварда не найдено. `profile_routes.py` не даёт mass-assignment (схема обновления явно исключает `login`/`role`). JWT (`auth_handler.py`) — корректные проверки expiry/алгоритма.
