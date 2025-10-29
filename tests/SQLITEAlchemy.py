import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, ForeignKey ,  DateTime
from datetime import datetime


class Base(DeclarativeBase):
    pass

class Chats(Base):

    __tablename__ = "chats"

    chat_id: Mapped[int] = mapped_column(String(100),primary_key=True)
    user_id: Mapped[int] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Messages(Base):

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(String(100),ForeignKey('chats.chat_id'))
    role: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Users(Base):

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(String(100))
    login: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)





# Используем SQLite в файле
DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(DATABASE_URL, echo=True)

# Асинхронная функция для создания таблиц
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Запуск
asyncio.run(create_tables())
