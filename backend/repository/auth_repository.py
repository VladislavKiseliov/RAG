import uuid

from backend.repository.base_repository import BaseRepository


from typing import Optional
from datetime import datetime

from sqlalchemy import select, update

from backend.models.database_models import  Users, RefreshTokens

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

    async def add_refresh_token(self, user_id: int, token: str, expires_at: datetime) -> None:
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

    async def revoke_all_user_tokens(self, user_id: int) -> int:
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

    async def get_user_by_id(self, user_id: int) -> Optional[Users]:
        result = await self._session.get(Users, user_id)
        return result

    async def get_user_by_guid(self, user_guid: uuid.UUID) -> Optional[Users]:
        stmt = select(Users).where(Users.guid == user_guid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user(self, login: str) -> Optional[Users]:
        stmt = select(Users).where(Users.login == login)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()