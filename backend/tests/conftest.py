from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import insert, delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from backend.models.database_models import (
    SCHEMA, ChatType, Chats, Messages, RefreshTokens, Users, chat_participant,
)
from backend.repository.auth_repository import AuthRepository
from backend.repository.chat_repository import ChatRepository
from backend.repository.messages_repository import MessageRepository
from backend.repository.messenger_repository import MessengerRepository
from backend.repository.note_repository import NoteRepository
from backend.repository.user_repository import UserRepository

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

# ── Фиксированные GUIDs — детерминированные данные для тестов ────────────────
ALICE_GUID    = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-000000000001")
BOB_GUID      = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-000000000002")
CAROL_GUID    = uuid.UUID("cccccccc-cccc-cccc-cccc-000000000003")
AI_CHAT_GUID  = uuid.UUID("a1a1a1a1-a1a1-a1a1-a1a1-000000000010")
DIR_CHAT_GUID = uuid.UUID("d1d1d1d1-d1d1-d1d1-d1d1-000000000020")


# ── Seed-данные под текущую схему database_models.py ─────────────────────────
#
# Users: id (int autoincrement), guid (UUID), login, password, first_name, last_name
# Chats: id (int autoincrement), guid (UUID), chat_type, created_by_id (int FK)
# chat_participant: user_id (int FK), chat_id (int FK)  — M2M
# Messages: id (int autoincrement), guid (UUID), chat_id (int FK), user_id (int FK nullable),
#           role (str nullable), content (Text)

_SEED_USERS = [
    {
        "id": 1, "guid": ALICE_GUID, "login": "alice", "password": "hashed-alice",
        "first_name": "Alice", "last_name": "Smith",
        "is_active": True, "is_deleted": False, "is_superuser": False, "role": "user",
    },
    {
        "id": 2, "guid": BOB_GUID, "login": "bob", "password": "hashed-bob",
        "first_name": "Bob", "last_name": "Jones",
        "is_active": True, "is_deleted": False, "is_superuser": False, "role": "user",
    },
    {
        "id": 3, "guid": CAROL_GUID, "login": "carol", "password": "hashed-carol",
        "first_name": "Carol", "last_name": "White",
        "is_active": True, "is_deleted": False, "is_superuser": False, "role": "user",
    },
]

_SEED_CHATS = [
    # AI-чат Алисы
    {
        "id": 1, "guid": AI_CHAT_GUID, "chat_type": ChatType.AI_DIRECT,
        "created_by_id": 1, "title": "AI чат Алисы",
    },
    # Прямой мессенджер-чат между Алисой и Бобом
    {
        "id": 2, "guid": DIR_CHAT_GUID, "chat_type": ChatType.DIRECT,
        "created_by_id": 1, "title": None,
    },
]

_SEED_PARTICIPANTS = [
    {"user_id": 1, "chat_id": 1},   # Alice → AI чат
    {"user_id": 1, "chat_id": 2},   # Alice → direct чат
    {"user_id": 2, "chat_id": 2},   # Bob   → direct чат
]

_SEED_MESSAGES = [
    # AI-чат: role заполнен, user_id = None для ответа ассистента
    {"id": 1, "chat_id": 1, "user_id": 1,    "role": "user",      "content": "Привет, AI!"},
    {"id": 2, "chat_id": 1, "user_id": None,  "role": "assistant", "content": "Чем могу помочь?"},
    # Мессенджер: role = None, оба участника
    {"id": 3, "chat_id": 2, "user_id": 1, "role": None, "content": "Привет, Боб!"},
    {"id": 4, "chat_id": 2, "user_id": 2, "role": None, "content": "Привет, Алиса!"},
]


# ── Контейнер + схема (session-scoped) ────────────────────────────────────────
# Postgres поднимается кодом (testcontainers), схему накатывают реальные Alembic-
# миграции (ini_section="users") — не create_all/drop_all по ORM-метаданным, чтобы
# тестовая схема не могла разойтись с тем, что реально накатывает `alembic upgrade
# head` в проде. См. TESTING.md §3.

@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:18") as pg:
        yield pg


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema(pg_container):
    cfg = Config(str(ALEMBIC_INI), ini_section="users")
    cfg.set_main_option("sqlalchemy.url", pg_container.get_connection_url())
    command.upgrade(cfg, "head")


# ── Engine + seed-данные (session-scoped) ─────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def engine(pg_container, _migrated_schema):
    async_url = pg_container.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")
    engine = create_async_engine(async_url, future=True, echo=False)

    seed_sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with seed_sf() as session:
        await session.execute(insert(Users).values(_SEED_USERS))
        await session.execute(insert(Chats).values(_SEED_CHATS))
        await session.execute(insert(chat_participant).values(_SEED_PARTICIPANTS))
        await session.execute(insert(Messages).values(_SEED_MESSAGES))
        await session.commit()

        # Явно вставленные seed id (1,2,3...) не продвигают identity-последовательность —
        # следующий autoincrement для fixture-based юзеров (test_user и т.п.) снова
        # целится в занятый id и падает UniqueViolationError.
        for table in ("users", "chats", "messages"):
            await session.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{SCHEMA}.{table}', 'id'), "
                f"(SELECT MAX(id) FROM {SCHEMA}.{table}))"
            ))
        await session.commit()

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ── Вспомогательный враппер: открывает новую транзакцию на каждый вызов ──────

class _IsolatedRepo:
    """Каждый метод выполняется в отдельной сессии+транзакции — тесты изолированы."""
    def __init__(self, repo_cls, session_factory):
        self._cls = repo_cls
        self._sf = session_factory

    def __getattr__(self, name):
        sf, cls = self._sf, self._cls

        async def _call(*args, **kwargs):
            async with sf() as session:
                async with session.begin():
                    return await getattr(cls(session), name)(*args, **kwargs)

        return _call


# ── Репозиторные fixtures ─────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def auth_repository(session_factory) -> AuthRepository:
    return _IsolatedRepo(AuthRepository, session_factory)


@pytest_asyncio.fixture
async def user_repository(session_factory) -> UserRepository:
    return _IsolatedRepo(UserRepository, session_factory)


@pytest_asyncio.fixture
async def chat_repository(session_factory) -> ChatRepository:
    return _IsolatedRepo(ChatRepository, session_factory)


@pytest_asyncio.fixture
async def message_repository(session_factory) -> MessageRepository:
    return _IsolatedRepo(MessageRepository, session_factory)


@pytest_asyncio.fixture
async def messenger_repository(session_factory) -> MessengerRepository:
    return _IsolatedRepo(MessengerRepository, session_factory)


@pytest_asyncio.fixture
async def note_repository(session_factory) -> NoteRepository:
    return _IsolatedRepo(NoteRepository, session_factory)


# ── Fake UnitOfWork — для unit-тестов сервисов, инжектящих uow_factory ────────
# Один и тот же экземпляр возвращается при каждом вызове фабрики, чтобы вызовы
# `async with self._uow_factory() as uow` внутри одного сервисного метода (их может
# быть несколько подряд) писали в один и тот же мок и были видны для assert-ов.

class FakeUnitOfWork:
    def __init__(self):
        self.chats = AsyncMock()
        self.messages = AsyncMock()
        self.auth = AsyncMock()
        self.messenger = AsyncMock()
        self.notes = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.refresh = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, *args):
        return False


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def fake_uow_factory(fake_uow: FakeUnitOfWork):
    return lambda: fake_uow


# ── E2E: реальное FastAPI-приложение поверх testcontainers-БД ────────────────
# Импорты внутри тел фикстур (не на уровне модуля) - чтобы unit-тесты, не
# запрашивающие эти фикстуры, не платили за импорт всего backend.main/роутеров.

@pytest_asyncio.fixture
async def backend_container(pg_container):
    """BackendContainer вручную, не через build_backend_infrastructure() - та
    читает settings.DATABASE_URL (реальная БД из .env), а не testcontainers.

    Собственный engine, НЕ общая сессионная фикстура engine/session_factory:
    TestClient гоняет приложение в своём фоновом треде/event loop - asyncpg-
    соединения из общего engine к этому моменту уже loop-bound на обычный
    pytest-asyncio loop (им уже попользовались другие тесты в сессии), и падают
    с "attached to a different loop" при вызове из TestClient-потока. Этот
    engine не делает ни одного запроса до того, как TestClient примет управление,
    поэтому первый реальный чекаут соединения происходит уже в его loop'е."""
    from backend.infrastructure import BackendContainer
    from backend.services.ai.llm_client import LLMClient
    from backend.services.auth_handler import AuthHandler
    from backend.services.messenger.websocket_handlers import register_handlers
    from backend.services.messenger.websocket_manager import WebSocketManager

    async_url = pg_container.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")
    dedicated_engine = create_async_engine(async_url, future=True, echo=False)
    dedicated_session_factory = async_sessionmaker(dedicated_engine, expire_on_commit=False, class_=AsyncSession)

    socket_manager = WebSocketManager()
    register_handlers(socket_manager)  # main.py::lifespan делает это на СВОЁМ контейнере, не на этом

    try:
        yield BackendContainer(
            engine=dedicated_engine,
            session_factory=dedicated_session_factory,
            auth_handler=AuthHandler(
                secret_key="test-secret-key-at-least-32-bytes-long",
                algorithm="HS256",
                expire_minutes=15,
                refresh_expire_days=7,
            ),
            llm_client=LLMClient(service_url="http://unreachable.invalid"),
            socket_manager=socket_manager,
        )
    finally:
        await dedicated_engine.dispose()


@pytest.fixture
def api_client(backend_container):
    """TestClient (не ASGITransport - тот не гоняет lifespan) с get_container,
    переопределённым на testcontainers-based backend_container."""
    from starlette.testclient import TestClient

    from backend.dependencies import get_container
    from backend.main import app

    app.dependency_overrides[get_container] = lambda: backend_container
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_container, None)


@pytest.fixture
def make_token(backend_container):
    """Токен через AuthHandler напрямую, не через /auth/login - test_user/
    test_user_bob хранят пароль как plaintext, verify_password с ним не пройдёт."""
    def _make(user: Users) -> str:
        return backend_container.auth_handler.create_access_token(str(user.guid))
    return _make


# ── Объекты из seed-данных (быстро, без лишних запросов) ─────────────────────

@pytest_asyncio.fixture
async def alice(session_factory) -> Users:
    async with session_factory() as session:
        return await session.get(Users, 1)


@pytest_asyncio.fixture
async def bob(session_factory) -> Users:
    async with session_factory() as session:
        return await session.get(Users, 2)


@pytest_asyncio.fixture
async def ai_chat(session_factory) -> Chats:
    async with session_factory() as session:
        return await session.get(Chats, 1)


@pytest_asyncio.fixture
async def direct_chat(session_factory) -> Chats:
    async with session_factory() as session:
        return await session.get(Chats, 2)


# ── Изолированные fixtures (создают/удаляют данные per-test) ─────────────────

@pytest_asyncio.fixture
async def test_user(session_factory) -> Users:
    """Свежий пользователь на каждый тест. Удаляется после (CASCADE чистит токены и участие в чатах)."""
    user = Users(
        login=f"test-{uuid.uuid4()}",
        password="test-password",
        first_name="Test",
        last_name="User",
        is_active=True,
        is_deleted=False,
    )
    async with session_factory() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)

    try:
        yield user
    finally:
        async with session_factory() as session:
            await session.execute(delete(Users).where(Users.id == user.id))
            await session.commit()


@pytest_asyncio.fixture
async def test_user_bob(session_factory) -> Users:
    """Второй свежий пользователь — для тестов с двумя участниками."""
    user = Users(
        login=f"test-bob-{uuid.uuid4()}",
        password="test-password",
        first_name="TestBob",
        last_name="Tester",
        is_active=True,
        is_deleted=False,
    )
    async with session_factory() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)

    try:
        yield user
    finally:
        async with session_factory() as session:
            await session.execute(delete(Users).where(Users.id == user.id))
            await session.commit()


@pytest_asyncio.fixture
async def test_ai_chat(session_factory, test_user: Users) -> Chats:
    """AI-чат, созданный test_user. CASCADE удалит сообщения при удалении чата."""
    chat = Chats(
        chat_type=ChatType.AI_DIRECT,
        created_by_id=test_user.id,
        title="Test AI Chat",
    )
    async with session_factory() as session:
        session.add(chat)
        await session.flush()
        await session.execute(
            insert(chat_participant).values(user_id=test_user.id, chat_id=chat.id)
        )
        await session.commit()
        await session.refresh(chat)

    try:
        yield chat
    finally:
        async with session_factory() as session:
            await session.execute(delete(Chats).where(Chats.id == chat.id))
            await session.commit()


@pytest_asyncio.fixture
async def test_direct_chat(session_factory, test_user: Users, test_user_bob: Users) -> Chats:
    """DIRECT-чат между test_user и test_user_bob."""
    chat = Chats(
        chat_type=ChatType.DIRECT,
        created_by_id=test_user.id,
        title=None,
    )
    async with session_factory() as session:
        session.add(chat)
        await session.flush()
        await session.execute(insert(chat_participant).values([
            {"user_id": test_user.id, "chat_id": chat.id},
            {"user_id": test_user_bob.id, "chat_id": chat.id},
        ]))
        await session.commit()
        await session.refresh(chat)

    try:
        yield chat
    finally:
        async with session_factory() as session:
            await session.execute(delete(Chats).where(Chats.id == chat.id))
            await session.commit()
