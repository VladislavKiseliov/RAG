from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def create_engine(db_url: str, *, echo: bool = False) -> AsyncEngine:
    """Создает AsyncEngine для asyncpg.

    Пример URL: postgresql+asyncpg://user:pass@host:5432/db
    """
    return create_async_engine(db_url, echo=echo, future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Фабрика AsyncSession с отключенным expire_on_commit."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def session_scope(session_factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """Асинхронный контекстный генератор сессии."""
    async with session_factory() as session:
        yield session
