from __future__ import annotations

import uuid

import pytest_asyncio
import uuid6
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models.database_models import Chats, RefreshTokens, Users
from backend.repository.repository import AuthRepository, ChatRepository, MessageRepository, UserRepository

DATABASE_URL = "postgresql+asyncpg://myuser:mypassword@localhost:5432/myapp_db"


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(DATABASE_URL, future=True, echo=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
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
