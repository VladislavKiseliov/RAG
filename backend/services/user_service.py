from typing import Any
from uuid import UUID

from backend.repository.repository import UserRepository


class UserService:
    """Сервис работы с пользователями для админ-роутов."""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    @staticmethod
    def _to_payload(user: Any) -> dict[str, Any]:
        return {
            "id": str(user.id),
            "login": user.login,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    async def get_users_repo(self, page_size: int) -> dict[str, Any]:
        users = await self.user_repo.get_users(page_size=page_size)
        return {
            "items": [self._to_payload(user) for user in users],
            "total": len(users),
            "page_size": page_size,
        }

    async def get_user_repo_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        user = await self.user_repo.get_user_by_id(user_id)
        if user is None:
            return None
        return self._to_payload(user)

    async def create_user_repo(self, login: str, password: str) -> dict[str, Any]:
        existing = await self.user_repo.get_user_by_login(login)
        if existing is not None:
            raise ValueError("User with this login already exists")

        user = await self.user_repo.create_user(login=login, password=password)
        return self._to_payload(user)

    async def update_user_repo(self, user_id: UUID, login: str, password: str) -> dict[str, Any] | None:
        existing = await self.user_repo.get_user_by_login(login)
        if existing is not None and existing.id != user_id:
            raise ValueError("User with this login already exists")

        updated = await self.user_repo.update_user(
            user_id=user_id,
            new_login=login,
            new_password=password,
        )
        if not updated:
            return None

        user = await self.user_repo.get_user_by_id(user_id)
        if user is None:
            return None
        return self._to_payload(user)

    async def delete_user_repo(self, user_id: UUID) -> bool:
        return await self.user_repo.delete_user(user_id)
