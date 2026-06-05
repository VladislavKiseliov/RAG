# Messenger — План интеграции

Групповой мессенджер поверх существующего FastAPI бэкенда.
Референс: https://github.com/notarious2/fastapi-chat

---

## Шаг 1 — Redis в инфраструктуру

### `settings.py`
Добавить поля в `BackendSettings`:
```python
redis_host: str = "localhost"       # REDIS_HOST
redis_port: int = 6379              # REDIS_PORT
redis_password: str = ""            # REDIS_PASSWORD
redis_db: int = 0                   # REDIS_DB
```
Добавить property `REDIS_URL`:
```python
@property
def REDIS_URL(self) -> str:
    if self.redis_password:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
    return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
```

### `infrastructure.py`
Добавить в `BackendContainer`:
```python
redis_pool: aioredis.ConnectionPool
```
В `build_backend_infrastructure()`:
```python
redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=20,
    decode_responses=False,
)
```
Импорт: `import redis.asyncio as aioredis`

### `main.py`
В `lifespan` после создания контейнера:
```python
from backend.managers.websocket_manager import WebSocketManager

socket_manager = WebSocketManager(redis_pool=container.redis_pool)
app.state.socket_manager = socket_manager

# Регистрация handlers (из messenger_handlers.py)
from backend.websocket.messenger_handlers import register_handlers
register_handlers(socket_manager)
```
При shutdown закрыть пул:
```python
await container.redis_pool.aclose()
```

### `dependencies.py`
Добавить две зависимости:
```python
async def get_socket_manager(request: Request) -> WebSocketManager:
    return request.app.state.socket_manager

async def get_redis(request: Request) -> aioredis.Redis:
    return aioredis.Redis(connection_pool=request.app.state.container.redis_pool)

SocketManagerDep = Annotated[WebSocketManager, Depends(get_socket_manager)]
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]
```

---

## Шаг 2 — Модели БД

### Новый файл `models/messenger_models.py`

Три таблицы в схеме `messenger_schema`:

```python
class GroupChat(Base):
    __tablename__ = "group_chats"
    __table_args__ = {"schema": "messenger_schema"}

    id: UUID (pk, default=uuid4)
    name: str
    description: str | None
    created_by: UUID (FK → users_shema.users.id, ondelete="SET NULL")
    created_at: datetime
    updated_at: datetime

class GroupParticipant(Base):
    __tablename__ = "group_participants"
    __table_args__ = {"schema": "messenger_schema"}

    id: int (pk, autoincrement)
    chat_id: UUID (FK → messenger_schema.group_chats.id, ondelete="CASCADE")
    user_id: UUID (FK → users_shema.users.id, ondelete="CASCADE")
    role: str  # "member" | "admin"
    joined_at: datetime
    # UniqueConstraint(chat_id, user_id)

class GroupMessage(Base):
    __tablename__ = "group_messages"
    __table_args__ = {"schema": "messenger_schema"}

    id: UUID (pk, default=uuid7)
    chat_id: UUID (FK → messenger_schema.group_chats.id, ondelete="CASCADE")
    user_id: UUID (FK → users_shema.users.id, ondelete="SET NULL")
    content: str (Text)
    created_at: datetime
    # Index: (chat_id, id)
```

### Миграция Alembic
```bash
alembic -c alembic.ini revision --autogenerate -m "add_messenger_schema"
# Проверить что в миграции есть CREATE SCHEMA IF NOT EXISTS messenger_schema
alembic -c alembic.ini upgrade head
```

Убедиться что в `migrations/env.py` подключены `messenger_models.py`.

---

## Шаг 3 — Managers

### Новый файл `managers/websocket_manager.py`

Адаптация из fastapi-chat. Изменение одно: `redis_pool` через конструктор.

```python
class WebSocketManager:
    def __init__(self, redis_pool):
        self.handlers: dict = {}
        self.chats: dict[str, set[WebSocket]] = {}
        self.user_to_websockets: dict[str, set[WebSocket]] = {}
        self.pubsub_client = RedisPubSubManager(redis_pool=redis_pool)
```

Методы (скопировать из референса, адаптировать):
- `connect_socket(websocket)` — accept
- `add_user_to_chat(chat_id, websocket)` — подписка на Redis канал
- `remove_user_from_chat(chat_id, websocket)` — отписка
- `broadcast_to_chat(chat_id, message)` — publish в Redis
- `_pubsub_data_reader(pubsub_subscriber)` — фоновый reader
- `send_error(message, websocket)` — отправить ошибку клиенту

### Новый файл `managers/pubsub_manager.py`

Адаптация из fastapi-chat. Принимает `redis_pool` в конструктор:

```python
class RedisPubSubManager:
    def __init__(self, redis_pool):
        self._redis_pool = redis_pool
        self.pubsub = None

    async def connect(self):
        redis = aioredis.Redis(connection_pool=self._redis_pool)
        self.pubsub = redis.pubsub()

    async def subscribe(self, channel: str): ...
    async def unsubscribe(self, channel: str): ...
    async def publish(self, channel: str, message: str): ...
```

---

## Шаг 4 — WebSocket роутер

### Новый файл `websocket/messenger_router.py`

Единственный WS-эндпоинт: `GET /ws/messenger/`

Токен передаётся как query-параметр (браузер не умеет кастомные заголовки в WS):
```
ws://host/ws/messenger/?token=<access_token>
```

Логика подключения:
```python
@router.websocket("/ws/messenger/")
async def messenger_ws(
    websocket: WebSocket,
    token: str = Query(...),
    socket_manager: WebSocketManager = Depends(get_socket_manager),
    db: AsyncSession = Depends(get_session),
):
    # 1. Аутентификация через существующий AuthService
    try:
        current_user = await auth_service.get_user_from_token(token)
    except (AuthenticationError, UserNotFoundError):
        await websocket.close(code=4001)
        return

    await socket_manager.connect_socket(websocket)

    # 2. Загрузить список групп пользователя из БД
    chats = await messenger_repo.get_user_chats(current_user.id)

    # 3. Подписать соединение на каналы чатов
    for chat in chats:
        await socket_manager.add_user_to_chat(str(chat.id), websocket)

    # 4. Основной цикл
    try:
        while True:
            incoming = await websocket.receive_json()
            message_type = incoming.get("type")
            handler = socket_manager.handlers.get(message_type)
            if not handler:
                await socket_manager.send_error(f"Unknown type: {message_type}", websocket)
                continue
            await handler(
                websocket=websocket,
                db=db,
                incoming=incoming,
                current_user=current_user,
                socket_manager=socket_manager,
                chats=chats,
            )
    except WebSocketDisconnect:
        for chat in chats:
            await socket_manager.remove_user_from_chat(str(chat.id), websocket)
```

---

## Шаг 5 — Handlers

### Новый файл `websocket/messenger_handlers.py`

Три handler-а + функция регистрации:

```python
def register_handlers(socket_manager: WebSocketManager):
    socket_manager.handlers["new_message"] = new_message_handler
    socket_manager.handlers["user_typing"] = user_typing_handler
    socket_manager.handlers["message_read"] = message_read_handler
```

**`new_message_handler`**:
1. Распарсить `chat_id`, `content` из incoming
2. Проверить что `current_user` — участник чата (`messenger_repo.is_participant`)
3. Сохранить `GroupMessage` в PostgreSQL
4. После успешного сохранения — `socket_manager.broadcast_to_chat(chat_id, message_dict)`

Формат исходящего сообщения:
```json
{
  "type": "new_message",
  "message_id": "uuid",
  "chat_id": "uuid",
  "user_id": "uuid",
  "content": "текст",
  "created_at": "iso8601"
}
```

**`user_typing_handler`**:
1. Проверить участие в чате
2. Broadcast `{"type": "user_typing", "chat_id": "...", "user_id": "..."}` — без сохранения в БД

**`message_read_handler`**:
1. Обновить статус прочтения (или просто логировать — зависит от требований)
2. Broadcast `{"type": "message_read", "chat_id": "...", "user_id": "...", "message_id": "..."}`

---

## Шаг 6 — Repository

### Новый файл `repository/messenger_repository.py`

```python
class MessengerRepository:
    def __init__(self, session: AsyncSession): ...

    async def get_user_chats(self, user_id: UUID) -> list[GroupChat]:
        # SELECT gc.* FROM group_chats gc
        # JOIN group_participants gp ON gc.id = gp.chat_id
        # WHERE gp.user_id = user_id

    async def is_participant(self, chat_id: UUID, user_id: UUID) -> bool: ...

    async def create_chat(self, name: str, creator_id: UUID) -> GroupChat: ...

    async def add_participant(self, chat_id: UUID, user_id: UUID, role: str = "member") -> GroupParticipant: ...

    async def remove_participant(self, chat_id: UUID, user_id: UUID) -> bool: ...

    async def create_message(self, chat_id: UUID, user_id: UUID, content: str) -> GroupMessage: ...

    async def get_messages(self, chat_id: UUID, limit: int = 50, before_id: UUID | None = None) -> list[GroupMessage]:
        # Пагинация — последние N сообщений, или до before_id

    async def get_chat_participants(self, chat_id: UUID) -> list[GroupParticipant]: ...
```

---

## Шаг 7 — HTTP API

### Новый файл `api/messenger_routes.py`

Все эндпоинты через Bearer токен (как везде в проекте).

```
POST   /api/messenger/chats                    — создать группу
GET    /api/messenger/chats                    — список групп пользователя
GET    /api/messenger/chats/{chat_id}/messages — история (с пагинацией)
POST   /api/messenger/chats/{chat_id}/participants         — добавить участника
DELETE /api/messenger/chats/{chat_id}/participants/{user_id} — удалить участника
GET    /api/messenger/chats/{chat_id}/participants         — список участников
```

### Подключить в `main.py`:
```python
from backend.api.messenger_routes import router as messenger_router
from backend.websocket.messenger_router import router as messenger_ws_router

app.include_router(messenger_router)
app.include_router(messenger_ws_router)
```

---

## Шаг 8 — Фронтенд

### `useMessenger.js`

```javascript
// Управляет WS соединением
// - подключается при монтировании
// - переподключается при разрыве через 2 сек
// - раздаёт события в стейт по type:
//   new_message → добавить в список сообщений активного чата
//   user_typing → показать индикатор
//   message_read → обновить статус
```

Токен берётся из localStorage/cookie и передаётся как query-параметр:
```javascript
const ws = new WebSocket(`ws://host/ws/messenger/?token=${token}`)
```

### `MessengerPage.jsx`

- Левая панель: список групп (загрузка через `GET /api/messenger/chats`)
- Правая панель: история сообщений + поле ввода
- История: `GET /api/messenger/chats/{id}/messages` при открытии чата
- Отправка: `ws.send(JSON.stringify({type: "new_message", chat_id, content}))`

### `App.jsx`

Добавить переключение между RAG-чатом и мессенджером — два раздела, не пересекаются.

---

## Порядок проверки каждого шага

| Шаг | Как проверить |
|-----|---------------|
| 1. Redis | `GET /admin/system/health` — Redis должен быть green |
| 2. Модели | Миграция прошла без ошибок, таблицы видны в БД |
| 3. Managers | Unit-тест: создать WS, подписать на канал, publish, проверить доставку |
| 4. WS роутер | Подключиться через wscat: `wscat -c "ws://localhost:8000/ws/messenger/?token=..."` |
| 5. Handlers | Отправить `{"type": "new_message", ...}`, проверить запись в БД и broadcast |
| 6. Repository | Через pytest: создать чат, добавить участника, создать сообщение |
| 7. HTTP API | Postman / curl — CRUD операции |
| 8. Фронт | Открыть два браузера, убедиться что сообщение доходит в реальном времени |

---

## Зависимости для установки

```
redis>=5.0.0
```
Уже есть в requirements (Redis используется Celery в rag_service). Проверить что `redis.asyncio` доступен.