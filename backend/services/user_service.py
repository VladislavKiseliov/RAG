from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.repository.repository import UserRepository
from backend.utils.exceptions import UserAlreadyExistsError


class UserService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    @staticmethod
    def _to_payload(user: Any) -> dict[str, Any]:
        return {
            "id": str(user.id),
            "login": user.login,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
        }

    async def get_users_repo(self, page_size: int) -> dict[str, Any]:
        async with self._sf() as session:
            users = await UserRepository(session).get_users(page_size=page_size)
            return {
                "items": [self._to_payload(u) for u in users],
                "total": len(users),
                "page_size": page_size,
            }

    async def get_user_repo_by_id(self, user_id: UUID) -> dict[str, Any] | None:
        async with self._sf() as session:
            user = await UserRepository(session).get_user_by_id(user_id)
            if user is None:
                return None
            return self._to_payload(user)

    async def create_user_repo(self, login: str, password: str) -> dict[str, Any]:
        async with self._sf() as session:
            existing = await UserRepository(session).get_user_by_login(login)

        if existing is not None:
            raise UserAlreadyExistsError()

        async with self._sf() as session:
            async with session.begin():
                user = await UserRepository(session).create_user(login=login, password=password)
            return self._to_payload(user)

    async def update_user_repo(self, user_id: UUID, login: str, password: str) -> dict[str, Any] | None:
        async with self._sf() as session:
            existing = await UserRepository(session).get_user_by_login(login)

        if existing is not None and existing.id != user_id:
            raise UserAlreadyExistsError()

        async with self._sf() as session:
            async with session.begin():
                updated = await UserRepository(session).update_user(
                    user_id=user_id, new_login=login, new_password=password
                )

        if not updated:
            return None

        async with self._sf() as session:
            user = await UserRepository(session).get_user_by_id(user_id)
            if user is None:
                return None
            return self._to_payload(user)

    async def delete_user_repo(self, user_id: UUID) -> bool:
        async with self._sf() as session:
            async with session.begin():
                return await UserRepository(session).delete_user(user_id)