import uuid
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.schemas.schemas import UserProfile, UserProfileUpdateRequest
from backend.repository.user_repository import UserRepository
from backend.utils.exceptions import UserAlreadyExistsError, UserNotFoundError


class UserService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    @staticmethod
    def _to_payload(user: Any) -> dict[str, Any]:
        return {
            "id": str(user.id),
            "login": user.login,
            "role": "admin" if user.is_superuser else "user",
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

    async def get_user_repo_by_id(self, user_id: int) -> UserProfile:
        async with self._sf() as session:
            user = await UserRepository(session).get_user_by_id(user_id)
            if user is None:
                return None
            profile = UserProfile.model_validate(user)
            return profile.model_copy(update={"role": "admin" if user.is_superuser else "user"})

    async def create_user_repo(self, login: str, password: str) -> dict[str, Any]:
        async with self._sf() as session:
            existing = await UserRepository(session).get_user_by_login(login)

        if existing is not None:
            raise UserAlreadyExistsError()

        async with self._sf() as session:
            async with session.begin():
                user = await UserRepository(session).create_user(login=login, password=password)
            return self._to_payload(user)

    async def update_user_repo(self, user_id:uuid.UUID, user_profile:UserProfileUpdateRequest) -> UserProfile:

        user_profile_update= user_profile.model_dump(exclude_unset=True)

        async with self._sf() as session:
            async with session.begin():
                user = await UserRepository(session).update_user(user_id, user_profile_update)
                if user is None:
                    raise UserNotFoundError()
            await session.refresh(user)

        return UserProfile.model_validate(user)


    async def update_user_credentials(self, user_id: int, login: str, password: str) -> dict[str, Any] | None:
        """Admin-only: update login and password for a user."""
        async with self._sf() as session:
            existing = await UserRepository(session).get_user_by_login(login)

        if existing is not None and existing.id != user_id:
            raise UserAlreadyExistsError()

        async with self._sf() as session:
            async with session.begin():
                user = await UserRepository(session).update_user(user_id, {"login": login, "password": password})
                if user is None:
                    raise UserNotFoundError()
        return self._to_payload(user)

    async def delete_user_repo(self, user_id: int) -> bool:
        async with self._sf() as session:
            async with session.begin():
                return await UserRepository(session).delete_user(user_id)

    async def update_user_role(self, user_id: int, is_superuser: bool) -> dict[str, Any]:
        """Admin-only: promote or demote a user's admin privileges."""
        async with self._sf() as session:
            async with session.begin():
                user = await UserRepository(session).update_user(user_id, {"is_superuser": is_superuser})
                if user is None:
                    raise UserNotFoundError()
        return self._to_payload(user)

    async def search_users(self, query: str, exclude_id: int) -> list[dict]:
        async with self._sf() as session:
            users = await UserRepository(session).search_users(query=query, exclude_id=exclude_id)
        return [
            {
                "guid": str(u.guid),
                "first_name": u.first_name,
                "last_name": u.last_name,
                "login": u.login,
                "job_title": u.job_title,
            }
            for u in users
        ]