from uuid import UUID

from huggingface_hub import User

from backend.repository.repository import UserRepository


class ChatService:
    """
    Сервис для управления чатами и сообщениями.
    Работает с автономными репозиториями, не удерживая сессию БД.
    """

    def __init__(self, user_repo: UserRepository):
        self.chat_repo = user_repo


    async def get_users(self,page,page_size:int =10) -> UserRepository:
        pass

    async def get_user(self, user_id: UUID) -> User:
        pass

    async def create_user(self, user: User):
        pass

    async def update_user(self, user: User):
        pass

    async def delete_user(self, user: User):
        pass


