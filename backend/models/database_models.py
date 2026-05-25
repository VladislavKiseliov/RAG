from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, DateTime, UUID, Text, Boolean, Integer, Index
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime, timezone
import uuid
import uuid6


class Base(DeclarativeBase):
    pass


class Users(Base):
    __tablename__ = "users"
    __table_args__ = ({"schema": "users_shema"},)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

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
        onupdate=lambda: datetime.now(timezone.utc)
    )
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    patronymic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)


class Chats(Base):
    __tablename__ = "chats"
    __table_args__ = ({"schema": "users_shema"},)

    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid6.uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('users_shema.users.id', ondelete="CASCADE")
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

    summary: Mapped[str] = mapped_column(Text,nullable=True)
    summary_link: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),nullable=True)
    summary_count: Mapped[int] = mapped_column(Integer,nullable=True)

    user: Mapped["Users"] = relationship(back_populates="chats")


    messages: Mapped[list["Messages"]] = relationship(
        "Messages",
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class Messages(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_id_id", "chat_id", "id"),
        {"schema": "users_shema"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid6.uuid7
    )

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
    sources: Mapped[list[dict]] = mapped_column(JSONB, default=list,nullable=True)
    context: Mapped[str] = mapped_column(Text,nullable=True)
    total: Mapped[int] = mapped_column(Integer,nullable=True)

    # Обратная связь
    chat: Mapped["Chats"] = relationship(back_populates="messages")


class RefreshTokens(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = ({"schema": "users_shema"},)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('users_shema.users.id', ondelete="CASCADE")
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
