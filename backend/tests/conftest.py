from __future__ import annotations

import uuid

import pytest_asyncio
from sqlalchemy import insert, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.settings import settings
from backend.models.database_models import (
    Base, ChatType, Chats, Messages, RefreshTokens, Users, chat_participant,
)
from backend.repository.user_repository import (
    AuthRepository, ChatRepository, MessageRepository, MessengerRepository, UserRepository,
)

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


# ── Engine + schema (session-scoped) ─────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def engine():
    assert settings.MODE == "TEST", "Tests must run only with MODE=TEST"
    assert settings.TEST_DB_NAME == "test_myapp_db", "TEST_DB_NAME must be 'test_myapp_db'"

    engine = create_async_engine(settings.DATABASE_URL, future=True, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    seed_sf = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with seed_sf() as session:
        await session.execute(insert(Users).values(_SEED_USERS))
        await session.execute(insert(Chats).values(_SEED_CHATS))
        await session.execute(insert(chat_participant).values(_SEED_PARTICIPANTS))
        await session.execute(insert(Messages).values(_SEED_MESSAGES))
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