import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.repository.repository import AuthRepository
from backend.models.database_models import Users
from backend.utils.exceptions import (
    UserNotFoundError, InvalidCredentialsError, TokenRevokedError,
    TokenExpiredError, RefreshTokenError, UserAlreadyExistsError,
    AuthenticationError
)


class AuthService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], auth_handler):
        self._sf = session_factory
        self._auth = auth_handler

    async def login(self, login: str, password: str) -> dict:
        async with self._sf() as session:
            user = await AuthRepository(session).get_user_by_login(login)

        if user is None:
            raise UserNotFoundError(login)

        # bcrypt — CPU-heavy, вне сессии
        jwt_token = self._auth.authenticate_user(
            user_id=str(user.id),
            hashed_password=user.password,
            provided_password=password,
        )
        if not jwt_token:
            raise InvalidCredentialsError()

        refresh_token = secrets.token_urlsafe(48)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=7)

        async with self._sf() as session:
            async with session.begin():
                await AuthRepository(session).add_refresh_token(user.id, refresh_token, refresh_expires)

        return {
            "message": "Login successful",
            "access_token": jwt_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def register(self, username: str, password: str) -> dict:
        async with self._sf() as session:
            existing = await AuthRepository(session).get_user_by_login(username)

        if existing:
            raise UserAlreadyExistsError()

        hashed_password = self._auth.get_password_hash(password)

        async with self._sf() as session:
            async with session.begin():
                user = await AuthRepository(session).create_user(username, hashed_password)
            user_id = str(user.id)

        return {
            "status": "success",
            "message": "User created successfully",
            "user_id": user_id,
        }

    async def refresh(self, refresh_token: str) -> dict:
        async with self._sf() as session:
            stored = await AuthRepository(session).get_refresh_token(refresh_token)

        if not stored:
            raise RefreshTokenError("Token not found")
        if stored.revoked:
            raise TokenRevokedError()
        if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise TokenExpiredError()

        user_id = str(stored.user_id)
        new_access = self._auth.create_access_token(user_id)
        new_refresh = secrets.token_urlsafe(48)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=7)

        # revoke + add атомарно
        async with self._sf() as session:
            async with session.begin():
                repo = AuthRepository(session)
                await repo.revoke_refresh_token(refresh_token)
                await repo.add_refresh_token(stored.user_id, new_refresh, refresh_expires)

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
        }

    async def logout(self, refresh_token: str, revoke_all: bool = False) -> dict:
        async with self._sf() as session:
            stored = await AuthRepository(session).get_refresh_token(refresh_token)

        if not stored or stored.revoked:
            return {"status": "success", "message": "Already logged out"}

        async with self._sf() as session:
            async with session.begin():
                repo = AuthRepository(session)
                if revoke_all:
                    count = await repo.revoke_all_user_tokens(stored.user_id)
                    message = f"Logged out from all devices. Revoked {count} tokens."
                else:
                    await repo.revoke_refresh_token(refresh_token)
                    message = "Logged out successfully."

        return {"status": "success", "message": message}

    async def get_user_from_token(self, token: str) -> Users:
        payload = self._auth.decode_token(token)
        user_id_str = payload.get("sub")

        if not user_id_str:
            raise AuthenticationError("Invalid token claim")

        try:
            user_uuid = uuid.UUID(user_id_str)
        except ValueError:
            raise AuthenticationError("Invalid user identifier format")

        async with self._sf() as session:
            user = await AuthRepository(session).get_user_id(user_uuid)

        if not user:
            raise UserNotFoundError()

        return user