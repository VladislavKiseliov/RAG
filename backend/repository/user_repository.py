import enum
from typing import List, Optional, TypedDict, Dict
import uuid
from datetime import datetime, timezone


from sqlalchemy import select, update, delete, Select, func, and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.database_models import Users
from backend.repository.base_repository import BaseRepository


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

    async def search_users(self, query: str, exclude_id: int, limit: int = 20) -> list[Users]:
        pattern = f"%{query}%"
        stmt = (
            select(Users)
            .where(Users.id != exclude_id)
            .where(Users.is_active == True)
            .where(Users.is_deleted == False)
            .where(
                or_(
                    Users.first_name.ilike(pattern),
                    Users.last_name.ilike(pattern),
                    Users.login.ilike(pattern),
                )
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

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



