from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, DateTime, UUID, Text, Boolean
from datetime import datetime, timezone
import uuid


class Base(DeclarativeBase):
    pass


class Users(Base):
    __tablename__ = "users"
    __table_args__ = ({"schema": "users_shema"},)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4  # Можно без lambda, если это просто вызов функции
    )
    # Каскад здесь: если удалим пользователя, удалятся и его чаты
    chats: Mapped[list["Chats"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    login: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)  # Авто-обновление даты при изменении
    )


class Chats(Base):
    __tablename__ = "chats"
    __table_args__ = ({"schema": "users_shema"},)

    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('users_shema.users.id', ondelete="CASCADE")  # БД удалит чат, если удален юзер
    )
    title: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["Users"] = relationship(back_populates="chats")

    # СВЯЗЬ С СООБЩЕНИЯМИ + Каскад
    # passive_deletes=True позволяет SQLAlchemy не загружать сообщения в память при удалении чата
    messages: Mapped[list["Messages"]] = relationship(
        "Messages",
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class Messages(Base):
    __tablename__ = "messages"
    __table_args__ = ({"schema": "users_shema"},)

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # ГЛАВНОЕ ИЗМЕНЕНИЕ: ondelete="CASCADE"
        ForeignKey('users_shema.chats.chat_id', ondelete="CASCADE"),
        nullable=False
    )
    role: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Обратная связь (необязательно, но полезно)
    chat: Mapped["Chats"] = relationship(back_populates="messages")


class RefreshTokens(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = ({"schema": "users_shema"},)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('users_shema.users.id', ondelete="CASCADE")  # Токен удалится, если удален юзер
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
