from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column,relationship
from sqlalchemy import String, ForeignKey, DateTime, BigInteger
from datetime import datetime
from sqlalchemy import String
import uuid
import uuid6


class Base(DeclarativeBase):
    pass

class Users(Base):

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(String(36),primary_key=True,default=lambda: str(uuid.uuid4()))
    chats: Mapped[list["Chats"]] = relationship(back_populates="user")
    login: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Chats(Base):

    __tablename__ = "chats"

    chat_id: Mapped[uuid.UUID] = mapped_column(String(36),primary_key=True,default=lambda: str(uuid.uuid4()))
    user_id: Mapped[uuid.UUID] = mapped_column(String(36),ForeignKey('users.id'))
    title: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped[Users] = relationship(back_populates="chats")

class Messages(Base):

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger,ForeignKey('chats.chat_id'))
    role: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

