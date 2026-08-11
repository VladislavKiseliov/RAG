import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict

from backend.services.unit_of_work import UnitOfWork
from backend.utils.exceptions import (
    InvalidCredentialsError, TokenRevokedError,
    RefreshTokenExpiredError, RefreshTokenError, UserAlreadyExistsError,
    AuthenticationError, UserNotFoundError
)
from backend.utils.logger_config import setup_logger

logger = setup_logger(__name__)


@dataclass
class CurrentUser:
    """Authenticated user identity extracted from a JWT token.

    Passed through FastAPI dependencies to route handlers.
    Contains only the fields needed for request-scoped authorization.
    """
    id: int
    guid: uuid.UUID
    login: str
    first_name: str | None
    last_name: str | None
    is_superuser: bool


class AuthService:
    """Handles user authentication lifecycle: registration, login, token rotation, and logout.

    Depends on AuthRepository for models and an auth_handler for JWT and bcrypt operations.
    All DB interactions open short-lived sessions; bcrypt is intentionally called outside
    the session to avoid holding a connection during a CPU-heavy operation.
    """

    def __init__(self, uow_factory: Callable[[], UnitOfWork], auth_handler):
        self._uow_factory = uow_factory
        self._auth = auth_handler

    async def login(self, login: str, password: str) -> dict:
        """Authenticate a user and issue a JWT + refresh token pair.

        Args:
            login: The user's unique login name.
            password: Plain-text password to verify against the stored bcrypt hash.

        Returns:
            Dict with access_token, refresh_token, token_type, and a message.

        Raises:
            InvalidCredentialsError: If the login does not exist or the password is wrong.
                Both cases return the same error to avoid user enumeration.
        """

        async with self._uow_factory() as uow:
            user = await uow.auth.get_user(login)

        if user is None:
            logger.warning("Failed login attempt: user not found", extra={"user": login})
            raise InvalidCredentialsError()

        # bcrypt is CPU-heavy — called outside the session to release the DB connection first
        jwt_token = self._auth.authenticate_user(
            user_id=str(user.guid),
            hashed_password=user.password,
            provided_password=password,
        )
        if not jwt_token:
            logger.warning("Failed login attempt: wrong password", extra={"user": login})
            raise InvalidCredentialsError()

        refresh_token = secrets.token_urlsafe(48)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=7)

        async with self._uow_factory() as uow:
            await uow.auth.add_refresh_token(user_id=user.id, token=refresh_token, expires_at=refresh_expires)
            await uow.commit()


        logger.info("User logged in", extra={"user": login})
        return {
            "message": "Login successful",
            "access_token": jwt_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def register(self, username: str, password: str) -> dict:
        """Create a new user account with a bcrypt-hashed password.

        Args:
            username: Desired login name. Must be unique across all users.
            password: Plain-text password. Hashed before storage.

        Returns:
            Dict with status, message, and the new user's UUID.

        Raises:
            UserAlreadyExistsError: If a user with this login already exists.
        """
        async with self._uow_factory() as uow:
            existing = await uow.auth.get_user(username)

        if existing:
            raise UserAlreadyExistsError()

        hashed_password = self._auth.get_password_hash(password)

        async with self._uow_factory() as uow:
            user = await uow.auth.create_user(login=username, hashed_password=hashed_password)
            await uow.commit()
            user_id = str(user.id)


        logger.info("User registered", extra={"user": username})
        return {
            "status": "success",
            "message": "User created successfully",
            "user_id": user_id,
        }

    async def refresh(self, refresh_token: str) -> dict:
        """Rotate a refresh token and issue a new access + refresh token pair.

        Implements refresh token rotation: the old token is revoked and a new one
        is issued atomically within a single transaction.

        Args:
            refresh_token: The current valid refresh token.

        Returns:
            Dict with new access_token, refresh_token, and token_type.

        Raises:
            RefreshTokenError: If the token is not found in the database.
            TokenRevokedError: If the token has already been revoked.
            RefreshTokenExpiredError: If the token's expiry date has passed.
        """
        async with self._uow_factory() as uow:
            stored = await uow.auth.get_refresh_token(refresh_token)

        if not stored:
            raise RefreshTokenError("Token not found")
        if stored.revoked:
            raise TokenRevokedError()
        if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise RefreshTokenExpiredError()

        async with self._uow_factory() as uow:
            user = await uow.auth.get_user_by_id(stored.user_id)

        new_access = self._auth.create_access_token(str(user.guid))
        new_refresh = secrets.token_urlsafe(48)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=7)

        async with self._uow_factory() as uow:
            await uow.auth.revoke_refresh_token(token=refresh_token)
            await uow.auth.add_refresh_token(user_id=stored.user_id,
                                             token=new_refresh,
                                             expires_at=refresh_expires)
            await uow.commit()

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
        }

    async def logout(self, refresh_token: str, revoke_all: bool = False) -> Dict[str, str]:
        """Revoke a refresh token, optionally invalidating all active sessions.

        Idempotent: if the token is already revoked or not found, returns success silently.

        Args:
            refresh_token: The refresh token to revoke.
            revoke_all: If True, revokes all active refresh tokens for the user.

        Returns:
            Dict with status and a descriptive message.
        """
        async with self._uow_factory() as uow:
            stored = await uow.auth.get_refresh_token(refresh_token)

        if not stored or stored.revoked:
            return {"status": "success", "message": "Already logged out"}

        async with self._uow_factory() as uow:
            if revoke_all:
                count = await uow.auth.revoke_all_user_tokens(stored.user_id)
                message = f"Logged out from all devices. Revoked {count} tokens."
            else:
                await uow.auth.revoke_refresh_token(refresh_token)
                message = "Logged out successfully."
            await uow.commit()

        logger.info("User logged out", extra={"user_id": str(stored.user_id), "revoke_all": revoke_all})
        return {"status": "success", "message": message}

    async def get_user_from_token(self, token: str) -> CurrentUser:
        """Decode a JWT access token and return the authenticated user identity.

        Used as the core of the FastAPI dependency that protects authenticated routes.

        Args:
            token: Raw JWT access token from the Authorization header.

        Returns:
            CurrentUser with id and login extracted from the token and verified against DB.

        Raises:
            AuthenticationError: If the token is malformed, missing the sub claim,
                or contains an invalid UUID.
            UserNotFoundError: If the user_id from the token no longer exists in the DB.
        """
        payload = self._auth.decode_token(token)
        user_id_str = payload.get("sub")

        if not user_id_str:
            logger.warning("Invalid token: missing sub claim")
            raise AuthenticationError("Invalid token claim")

        try:
            user_guid = uuid.UUID(user_id_str)
        except ValueError:
            logger.warning("Invalid token: bad user_id format", extra={"sub": user_id_str})
            raise AuthenticationError("Invalid user identifier format")

        async with self._uow_factory() as uow:
            user = await uow.auth.get_user_by_guid(user_guid)

        if not user:
            raise UserNotFoundError()

        return CurrentUser(
            id=user.id,
            guid=user.guid,
            login=user.login,
            first_name=user.first_name,
            last_name=user.last_name,
            is_superuser=user.is_superuser,
        )
