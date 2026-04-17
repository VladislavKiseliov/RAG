import secrets
import uuid
from datetime import datetime, timedelta, timezone

from backend.repository.repository import AuthRepository
from backend.models.database_models import Users
from backend.utils.exceptions import (
    UserNotFoundError, InvalidCredentialsError, TokenRevokedError,
    TokenExpiredError, RefreshTokenError, UserAlreadyExistsError,
    AuthenticationError
)


class AuthService:
    """
    Сервис бизнес-логики аутентификации.
    Связывает работу с базой данных (через репозиторий) и логику безопасности (через auth_handler).
    """

    def __init__(self, repo: AuthRepository, auth_handler):

        self.repo = repo
        self._auth = auth_handler

    async def login(self, login: str, password: str) -> dict:
        """Аутентификация пользователя и выдача пары токенов."""
        user = await self.repo.get_user_by_login(login)
        if user is None:
            raise UserNotFoundError(login)

        # Проверка пароля — тяжелая операция, выполняется вне транзакции БД
        jwt_token = self._auth.authenticate_user(
            user_id=str(user.id),
            hashed_password=user.password,
            provided_password=password,
        )

        if not jwt_token:
            raise InvalidCredentialsError()

        # Генерация и сохранение Refresh токена
        refresh_token = secrets.token_urlsafe(48)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=7)

        # Репозиторий сам откроет и закроет сессию для записи токена
        await self.repo.add_refresh_token(user.id, refresh_token, refresh_expires)

        return {
            "message": "Login successful",
            "access_token": jwt_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def register(self, username: str, password: str) -> dict:
        """Регистрация нового пользователя с предварительной проверкой логина."""
        existing_user = await self.repo.get_user_by_login(username)
        if existing_user:
            raise UserAlreadyExistsError()

        hashed_password = self._auth.get_password_hash(password)

        # Атомарное создание пользователя внутри репозитория
        user = await self.repo.create_user(username, hashed_password)

        return {
            "status": "success",
            "message": "User created successfully",
            "user_id": str(user.id)
        }

    async def refresh(self, refresh_token: str) -> dict:
        """Обновление пары Access/Refresh токенов по валидному Refresh токену."""
        stored = await self.repo.get_refresh_token(refresh_token)

        if not stored:
            raise RefreshTokenError("Token not found")
        if stored.revoked:
            raise TokenRevokedError()
        # Приводим к UTC для корректного сравнения
        if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise TokenExpiredError()

        # Генерация новых данных
        user_id = str(stored.user_id)
        new_access = self._auth.create_access_token(user_id)
        new_refresh = secrets.token_urlsafe(48)
        refresh_expires = datetime.now(timezone.utc) + timedelta(days=7)

        # Отзываем старый и добавляем новый.
        # В этой архитектуре это два коротких независимых вызова БД.
        await self.repo.revoke_refresh_token(refresh_token)
        await self.repo.add_refresh_token(stored.user_id, new_refresh, refresh_expires)

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
        }

    async def logout(self, refresh_token: str, revoke_all: bool = False) -> dict:
        """Завершение сессии. Возможность отозвать все токены пользователя."""
        stored = await self.repo.get_refresh_token(refresh_token)

        if not stored or stored.revoked:
            return {"status": "success", "message": "Already logged out"}

        if revoke_all:
            # Безопасный выход со всех устройств
            count = await self.repo.revoke_all_user_tokens(stored.user_id)
            message = f"Logged out from all devices. Revoked {count} tokens."
        else:
            await self.repo.revoke_refresh_token(refresh_token)
            message = "Logged out successfully."

        return {"status": "success", "message": message}

    async def get_user_from_token(self, token: str) -> Users:
        """Валидация Access-токена и получение объекта пользователя."""
        payload = self._auth.decode_token(token)
        user_id_str = payload.get("sub")

        if not user_id_str:
            raise AuthenticationError("Invalid token claim")

        try:
            user_uuid = uuid.UUID(user_id_str)
            user = await self.repo.get_user_id(user_uuid)
        except ValueError:
            raise AuthenticationError("Invalid user identifier format")

        if not user:
            raise UserNotFoundError()

        return user