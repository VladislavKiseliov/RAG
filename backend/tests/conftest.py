from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest_asyncio
import uuid6
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.settings import settings
from backend.models.database_models import Base, Chats, Messages, RefreshTokens, Users
from backend.repository.repository import AuthRepository, ChatRepository, MessageRepository, UserRepository


def _read_mock_json(filename: str) -> list[dict]:
    with open(f"backend/tests/{filename}", encoding="utf-8") as file:
        return json.load(file)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

@pytest_asyncio.fixture(scope="session")
async def engine():
    assert settings.MODE == "TEST", "Tests must run only with MODE=TEST"
    assert settings.TEST_DB_NAME == "test_myapp_db", "TEST_DB_NAME must be 'test_myapp_db'"

    engine = create_async_engine(settings.DATABASE_URL, future=True, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    users = _read_mock_json("mock_users.json")
    chats = _read_mock_json("mock_chats.json")
    messages = _read_mock_json("mock_messages.json")
    refresh_tokens = _read_mock_json("mock_refresh_tokens.json")

    for token in refresh_tokens:
        token["expires_at"] = _parse_dt(token["expires_at"])

    seed_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with seed_session_factory() as session:
        for model, values in [
            (Users, users),
            (Chats, chats),
            (Messages, messages),
            (RefreshTokens, refresh_tokens),
        ]:
            await session.execute(insert(model).values(values))
        await session.commit()

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def auth_repository(session_factory) -> AuthRepository:
    return AuthRepository(session_factory)


@pytest_asyncio.fixture
async def user_repository(session_factory) -> UserRepository:
    return UserRepository(session_factory)


@pytest_asyncio.fixture
async def chat_repository(session_factory) -> ChatRepository:
    return ChatRepository(session_factory)


@pytest_asyncio.fixture
async def message_repository(session_factory) -> MessageRepository:
    return MessageRepository(session_factory)


@pytest_asyncio.fixture
async def test_user(session_factory) -> Users:
    user = Users(
        login=f"test-user-{uuid.uuid4()}",
        password="test-password",
    )

    async with session_factory() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)

    try:
        yield user
    finally:
        async with session_factory() as session:
            await session.execute(delete(RefreshTokens).where(RefreshTokens.user_id == user.id))
            await session.execute(delete(Chats).where(Chats.user_id == user.id))
            await session.execute(delete(Users).where(Users.id == user.id))
            await session.commit()


@pytest_asyncio.fixture
async def test_chat(session_factory, test_user: Users) -> Chats:
    chat = Chats(
        chat_id=uuid6.uuid7(),
        user_id=test_user.id,
        title="Тестовый чат",
    )

    async with session_factory() as session:
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

    return chat
