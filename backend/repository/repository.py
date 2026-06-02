import enum
from typing import List, Optional, TypedDict
import uuid
from datetime import datetime, timezone


from sqlalchemy import select, update, delete, Select, func
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
    """Base repository class. Session is injected externally; transactions are managed by the service layer."""

    def __init__(self, session: AsyncSession):
        self._session = session


class AuthRepository(BaseRepository):
    """Data access layer for authentication: user creation, lookup, and refresh token management."""

    async def create_user(self, login: str, hashed_password: str) -> Users:
        """Insert a new user row and flush to obtain the generated UUID.

        Args:
            login: Unique login name.
            hashed_password: bcrypt hash of the user's password.

        Returns:
            The newly created Users ORM object with id populated.
        """
        new_user = Users(login=login, password=hashed_password, is_active=True)
        self._session.add(new_user)
        await self._session.flush()
        return new_user

    async def get_user_by_login(self, login: str) -> Optional[Users]:
        """Look up a user by their unique login name.

        Args:
            login: The login to search for.

        Returns:
            Users object if found, None otherwise.
        """
        stmt = select(Users).where(Users.login == login)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_refresh_token(self, user_id: uuid.UUID, token: str, expires_at: datetime) -> None:
        """Persist a new refresh token linked to the given user.

        Args:
            user_id: Owner's UUID.
            token: Cryptographically random token string.
            expires_at: UTC datetime when the token becomes invalid.
        """
        refresh = RefreshTokens(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            revoked=False
        )
        self._session.add(refresh)

    async def get_refresh_token(self, token: str) -> Optional[RefreshTokens]:
        """Fetch a refresh token row by its value.

        Args:
            token: The raw token string.

        Returns:
            RefreshTokens object if found, None otherwise.
        """
        stmt = select(RefreshTokens).where(RefreshTokens.token == token)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> int:
        """Mark all active refresh tokens for a user as revoked.

        Args:
            user_id: The user whose tokens should be invalidated.

        Returns:
            Number of tokens that were revoked.
        """
        stmt = (
            update(RefreshTokens)
            .where(RefreshTokens.user_id == user_id, RefreshTokens.revoked == False)
            .values(revoked=True)
        )
        result = await self._session.execute(stmt)
        return result.rowcount

    async def revoke_refresh_token(self, token: str) -> bool:
        """Mark a single refresh token as revoked.

        Args:
            token: The token to invalidate.

        Returns:
            True if a row was updated, False if the token was not found.
        """
        stmt = update(RefreshTokens).where(RefreshTokens.token == token).values(revoked=True)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def get_user_id(self, user_id: uuid.UUID) -> Optional[Users]:
        """Look up a user by their UUID primary key.

        Args:
            user_id: The user's UUID.

        Returns:
            Users object if found, None otherwise.
        """
        stmt = select(Users).where(Users.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


class UserRepository(BaseRepository):
    """Data access layer for user profile management: CRUD operations on the Users table."""

    async def get_user_by_login(self, login: str) -> Optional[Users]:
        """Look up a user by login name.

        Args:
            login: Unique login to search for.

        Returns:
            Users object if found, None otherwise.
        """
        stmt = select(Users).where(Users.login == login)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[Users]:
        """Look up a user by UUID primary key.

        Args:
            user_id: The user's UUID.

        Returns:
            Users object if found, None otherwise.
        """
        stmt = select(Users).where(Users.id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_user(self, user_id: uuid.UUID) -> bool:
        """Delete a user row by UUID.

        Args:
            user_id: The user to delete.

        Returns:
            True if the row was deleted, False if the user was not found.
        """
        stmt = delete(Users).where(Users.id == user_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def get_users(self, page_size: int = 50) -> list[Users]:
        """Fetch a page of users ordered by insertion (no cursor, simple LIMIT).

        Args:
            page_size: Maximum number of rows to return. Defaults to 50, max 500.

        Returns:
            List of Users ORM objects.
        """
        stmt = select(Users).limit(page_size)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_user(self, login: str, password: str) -> Users:
        """Insert a new user row and flush to obtain the generated UUID.

        Args:
            login: Unique login name.
            password: Pre-hashed password string.

        Returns:
            The newly created Users ORM object with id populated.
        """
        user = Users(login=login, password=password)
        self._session.add(user)
        await self._session.flush()
        return user

    async def update_user(self, user_id: uuid.UUID, data: dict) -> Optional[Users]:
        """Apply a partial update to a user's profile fields.

        Fetches the user, sets only the fields present in data (via setattr),
        and returns the modified object. SQLAlchemy's Unit of Work will generate
        the UPDATE on commit.

        Args:
            user_id: UUID of the user to update.
            data: Dict of field names to new values (typically from model_dump(exclude_unset=True)).

        Returns:
            Updated Users object, or None if the user was not found.
        """
        user = await self.get_user_by_id(user_id)
        if user is None:
            return None

        for field, value in data.items():
            setattr(user, field, value)
        return user


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
            .order_by(Messages.id.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(self, chat_id: uuid.UUID, limit: int = 10) -> List[Messages]:
        stmt = (
            select(Messages)
            .where(Messages.chat_id == chat_id)
            .order_by(Messages.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def count_after(self, chat_id: uuid.UUID, after_id: uuid.UUID | None = None) -> int:
        stmt = select(func.count()).where(Messages.chat_id == chat_id)
        if after_id is not None:
            stmt = stmt.where(Messages.id > after_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def get_messages_after(self, chat_id: uuid.UUID, after_id: uuid.UUID | None = None, limit: int = 10) -> List[Messages]:
        stmt = select(Messages).where(Messages.chat_id == chat_id)
        if after_id is not None:
            stmt = stmt.where(Messages.id > after_id)
        stmt = stmt.order_by(Messages.id.asc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

