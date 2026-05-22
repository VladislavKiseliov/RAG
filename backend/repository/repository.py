import enum
from typing import List, Optional, TypedDict
import uuid
from datetime import datetime, timezone


from sqlalchemy import select, update, delete, Select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database_models import Chats, Messages, Users, RefreshTokens

class DocumentAlreadyExists(Exception):
    """Брошено при конфликте уникальности по file_hash."""
    def __init__(self, file_hash: str) -> None:
        super().__init__(f"Document with hash '{file_hash}' already exists")
        self.file_hash = file_hash

class DocumentListItemDTO(TypedDict):
    doc_id: str
    filename: str
    status: str
    size: int | None
    s3key: str | None
    created_at: str


class DocumentStatus(str, enum.Enum):
    processing = "processing"
    completed = "completed"
    error = "error"


class BaseRepository:
    """Базовый класс репозитория. Сессия передаётся снаружи, транзакции управляются сервисом."""
    def __init__(self, session: AsyncSession):
        self._session = session


class AuthRepository(BaseRepository):
    """Репозиторий для управления доступом и сессиями (Refresh-токены)."""

    async def create_user(self, login: str, hashed_password: str) -> Users:
        new_user = Users(login=login, password=hashed_password)
        self._session.add(new_user)
        await self._session.flush()
        return new_user

    async def get_user_by_login(self, login: str) -> Optional[Users]:
        stmt = select(Users).where(Users.login == login)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_refresh_token(self, user_id: uuid.UUID, token: str, expires_at: datetime) -> None:
        refresh = RefreshTokens(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            revoked=False
        )
        self._session.add(refresh)

    async def get_refresh_token(self, token: str) -> Optional[RefreshTokens]:
        stmt = select(RefreshTokens).where(RefreshTokens.token == token)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> int:
        stmt = (
            update(RefreshTokens)
            .where(RefreshTokens.user_id == user_id, RefreshTokens.revoked == False)
            .values(revoked=True)
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def revoke_refresh_token(self, token: str) -> bool:
        stmt = update(RefreshTokens).where(RefreshTokens.token == token).values(revoked=True)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def get_user_id(self, user_id: uuid.UUID) -> Optional[Users]:
        stmt = select(Users).where(Users.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class UserRepository(BaseRepository):
    """Управление данными профиля пользователя."""

    async def get_user_by_login(self, login: str) -> Optional[Users]:
        stmt = select(Users).where(Users.login == login)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[Users]:
        stmt = select(Users).where(Users.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_user(self, user_id: uuid.UUID) -> bool:
        stmt = delete(Users).where(Users.id == user_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def get_users(self, page_size: int = 50) -> list[Users]:
        stmt = select(Users).limit(page_size)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_user(self, login: str, password: str) -> Users:
        user = Users(login=login, password=password)
        self._session.add(user)
        await self._session.flush()
        return user

    async def update_user(self, user_id: uuid.UUID, new_login: str, new_password: str) -> bool:
        stmt = (
            update(Users)
            .where(Users.id == user_id)
            .values(login=new_login, password=new_password, updated_at=datetime.now(timezone.utc))
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class ChatRepository(BaseRepository):
    """Управление чатами (создание, переименование, удаление)."""

    async def create_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID, title: str) -> Chats:
        chat = Chats(chat_id=chat_id, user_id=user_id, title=title)
        self._session.add(chat)
        await self._session.flush()
        return chat

    async def get_all_chats(self, user_id: uuid.UUID) -> List[Chats]:
        stmt = select(Chats).where(Chats.user_id == user_id).order_by(Chats.updated_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        stmt = delete(Chats).where(Chats.chat_id == chat_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def update_chat_title(self, chat_id: uuid.UUID, user_id: uuid.UUID, new_title: str) -> bool:
        stmt = (
            update(Chats)
            .where(Chats.chat_id == chat_id, Chats.user_id == user_id)
            .values(title=new_title, updated_at=datetime.now())
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def update_summary_count(self, chat_id: uuid.UUID) -> bool:
        stmt = (
            update(Chats)
            .where(Chats.chat_id == chat_id, Chats.user_id == user_id)
            .values(title=new_title, updated_at=datetime.now())
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def get_chat(self,chat_id: uuid.UUID) -> Chats:
        stmt = select(Chats).where(Chats.chat_id == chat_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()



class MessageRepository(BaseRepository):
    """Работа с сообщениями внутри чатов."""

    async def add_message(self, chat_id: uuid.UUID, role: str, content: str, sources: list = None) -> Messages:
        message = Messages(chat_id=chat_id, role=role, content=content, sources=sources)
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_history(self, chat_id: uuid.UUID, limit: int = 50) -> List[Messages]:
        stmt = (
            select(Messages)
            .where(Messages.chat_id == chat_id)
            .order_by(Messages.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


    async def get_messages_after(self, chat_id:uuid.UUID, after_id:uuid.UUID, summary_batch_size=10):
          anchor_ts = select(Messages.created_at).where(Messages.id == after_id)

          stmt = (
              select(Messages)
              .where(Messages.chat_id == chat_id, Messages.created_at > anchor_ts.scalar_subquery())
              .order_by(Messages.created_at.asc())
              .limit(summary_batch_size)
          )
          result = await self._session.execute(stmt)
          return list(result.scalars().all())


class DocumentRepository(BaseRepository):

    async def get_document_by_hash(self, file_hash: str) -> DocumentListItemDTO | None:
        """Return a document by SHA-256 hash, or `None` if absent."""
        result = await self._session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.file_hash == file_hash))
        return result.scalar_one_or_none()

    async def get_document_by_id(self, doc_id: uuid.UUID) -> DocumentListItemDTO | None:
        """Return a document by UUID, or `None` if absent."""
        result = await self._session.execute(select(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id))
        return result.scalar_one_or_none()

    async def list_documents(
            self,
            *,
            limit: int,
            offset: int,
            status: str | None = None,
            filename: str | None = None,
            created_from: datetime | None = None,
            created_to: datetime | None = None,
    ) -> list[DocumentListItemDTO]:
        """List documents with pagination and optional filters."""
        query: Select = select(DocumentListItemDTO)

        if status:
            query = query.where(DocumentListItemDTO.status == status)
        if filename:
            query = query.where(DocumentListItemDTO.filename.ilike(f"%{filename}%"))
        if created_from is not None:
            query = query.where(DocumentListItemDTO.created_at >= created_from)
        if created_to is not None:
            query = query.where(DocumentListItemDTO.created_at <= created_to)

        query = query.order_by(DocumentListItemDTO.created_at.desc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def create_document(
            self,
            filename: str,
            file_hash: str,
            meta: dict | None,
            *,
            doc_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Create a document in `processing` status and return its id."""
        doc = DocumentListItemDTO(
            id=doc_id or uuid.uuid4(),
            filename=filename,
            file_hash=file_hash,
            meta=meta,
            status=DocumentStatus.processing,
        )
        self._session.add(doc)
        await self._session.flush()
        return doc.id

    async def set_status(
            self,
            doc_id: uuid.UUID,
            status: DocumentStatus,
            *,
            chunk_count: int | None = None,
    ) -> None:
        """Update document status and optionally its processed child chunk count."""
        values: dict[str, DocumentStatus | int] = {"status": status}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count

        await self._session.execute(
            update(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id).values(**values)
        )

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        """Delete document row; linked parent chunks are removed by cascade."""
        await self._session.execute(
            delete(DocumentListItemDTO).where(DocumentListItemDTO.id == doc_id)
        )