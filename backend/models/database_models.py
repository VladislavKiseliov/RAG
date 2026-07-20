import enum
import uuid
from datetime import datetime, timezone
from typing import List

import uuid6
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Index,
    Integer, String, Table, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SCHEMA = "users_shema"


class Base(DeclarativeBase):
    pass

class UserRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"

class ChatType(enum.Enum):
    DIRECT = "direct"       # личка между двумя людьми
    GROUP = "group"         # групповой чат
    AI_DIRECT = "ai_direct" # 1-на-1 с AI (сценарий 3)


class MessageType(enum.Enum):
    TEXT = "text"
    FILE = "file"


# M2M: один чат — много участников, один пользователь — много чатов
chat_participant = Table(
    "chat_participant",
    Base.metadata,
    Column("user_id", ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), primary_key=True),
    Column("chat_id", ForeignKey(f"{SCHEMA}.chats.id", ondelete="CASCADE"), primary_key=True),
    schema=SCHEMA,
)


class Users(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_user_on_email_login", "email", "login"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(128), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    patronymic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    job_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.departments.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Все чаты где пользователь участник (через join-таблицу)
    chats: Mapped[List["Chats"]] = relationship(secondary=chat_participant, back_populates="users")
    messages: Mapped[List["Messages"]] = relationship(back_populates="user")
    read_statuses: Mapped[List["ReadStatus"]] = relationship(back_populates="user")

    def __str__(self) -> str:
        return self.login


class Chats(Base):
    __tablename__ = "chats"
    __table_args__ = (
        Index("idx_chat_on_type", "chat_type"),
        Index("idx_chat_on_guid", "guid"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid6.uuid7)
    chat_type: Mapped[str] = mapped_column(Enum(ChatType, inherit_schema=True))
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Кто создал чат (для группы — организатор; для AI_DIRECT — владелец)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Накопленное саммари чата — AI использует его как контекст (работает для всех типов чатов)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_link: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    summary_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Участники чата через join-таблицу
    users: Mapped[List["Users"]] = relationship(secondary=chat_participant, back_populates="chats")
    messages: Mapped[List["Messages"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", passive_deletes=True
    )
    read_statuses: Mapped[List["ReadStatus"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", passive_deletes=True
    )

    def __str__(self) -> str:
        return f"{self.chat_type.value.title()} {self.guid}"


class Messages(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_message_on_chat_id", "chat_id"),
        Index("idx_message_on_user_id", "user_id"),
        Index("idx_message_on_chat_user", "chat_id", "user_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid6.uuid7)
    message_type: Mapped[str] = mapped_column(
        Enum(MessageType, inherit_schema=True), default=MessageType.TEXT
    )
    content: Mapped[str] = mapped_column(Text)

    # SET NULL при удалении пользователя — история чата сохраняется
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, inherit_schema=True), nullable=True)
    chat_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.chats.id", ondelete="CASCADE")
    )
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # RAG-поля: заполняются только для AI_DIRECT сообщений от ассистента
    sources: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    total: Mapped[int | None] = mapped_column(Integer, nullable=True)

    chat: Mapped["Chats"] = relationship(back_populates="messages")
    user: Mapped["Users"] = relationship(back_populates="messages")

    def __str__(self) -> str:
        return self.content[:50]


class ReadStatus(Base):
    __tablename__ = "read_status"
    __table_args__ = (
        Index("idx_read_status_on_chat_id", "chat_id"),
        Index("idx_read_status_on_user_id", "user_id"),
        UniqueConstraint("user_id", "chat_id", name="uq_read_status_user_chat"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # ID последнего прочитанного сообщения — всё что после него = непрочитано
    last_read_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.chats.id", ondelete="CASCADE"))

    chat: Mapped["Chats"] = relationship(back_populates="read_statuses")
    user: Mapped["Users"] = relationship(back_populates="read_statuses")

    def __str__(self) -> str:
        return f"User: {self.user_id}, Message: {self.last_read_message_id}"


class RefreshTokens(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = ({"schema": SCHEMA},)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.departments.id"), nullable=True
    )


class Notes(Base):
    """Личные заметки. backend владеет таблицей целиком; rag_service только
    векторизует текст (см. NoteVectorizationService) и не хранит метаданные."""
    __tablename__ = "notes"
    __table_args__ = (
        Index("idx_note_on_user_id", "user_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid6.uuid7)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"))

    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    links: Mapped[list] = mapped_column(JSONB, default=list)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    folder: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reminder: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    follow_up: Mapped[bool] = mapped_column(Boolean, default=False)

    # draft | indexing | indexed | error — см. NoteService.trigger_index/mark_indexed
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )