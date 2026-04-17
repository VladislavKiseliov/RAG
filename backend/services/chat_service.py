import uuid6
from uuid import UUID
from typing import List, Dict, Any

from backend.services.llm_client import get_llm_answer
from backend.utils.exceptions import UserNotFoundError, AuthDatabaseError
# Обрати внимание на импорты, теперь мы передаем репозитории в конструктор
from backend.repository.repository import ChatRepository, MessageRepository


class ChatService:
    """
    Сервис для управления чатами и сообщениями.
    Работает с автономными репозиториями, не удерживая сессию БД.
    """

    def __init__(self, chat_repo: ChatRepository, message_repo: MessageRepository):
        self.chat_repo = chat_repo
        self.message_repo = message_repo

    async def create_chat(self, user_id: UUID, title: str = "Новый чат") -> str:
        """Создает новый чат и сразу возвращает его ID."""
        chat_id = uuid6.uuid7()
        # Репозиторий сам откроет транзакцию, сделает add и commit
        result = await self.chat_repo.create_chat(chat_id = chat_id,user_id= user_id,title= title)

        if not result:
            raise AuthDatabaseError("Не удалось создать чат")

        return str(chat_id)

    async def get_all_previews(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Получает краткий список чатов пользователя для боковой панели."""
        chats = await self.chat_repo.get_all_chats(user_id)

        # SQLAlchemy объекты (Chats) удобно преобразовывать в dict
        previews = [
            {"id": str(chat.chat_id), "title": chat.title or "Новый чат"}
            for chat in chats
        ]
        return previews  # Сортировка уже должна быть в SQL (ORDER BY)

    async def rename_chat(self, user_id: UUID, chat_id: UUID, new_title: str) -> bool:
        """Меняет название чата, проверяя владельца."""
        updated = await self.chat_repo.update_chat_title(chat_id, user_id, new_title)
        if not updated:
            raise UserNotFoundError("Чат не найден или доступ запрещен")
        return True

    async def delete_chat(self, user_id: UUID, chat_id: UUID) -> bool:
        """Удаляет чат со всей историей (если настроено каскадное удаление)."""
        deleted = await self.chat_repo.delete_chat(chat_id, user_id)
        if not deleted:
            raise UserNotFoundError("Не удалось удалить чат")
        return True

    async def get_history(self, chat_id: UUID) -> List[Dict]:
        """Возвращает историю сообщений конкретного чата."""
        # Мы используем MessageRepository для работы с сообщениями
        messages = await self.message_repo.get_history(chat_id)

        return [
            {"role": msg.role, "content": msg.content, "sources": msg.sources, "created_at": msg.created_at}
            for msg in messages
        ]

    async def process_message(self, user_id: UUID, chat_id: UUID, content: str) -> Dict:
        """
        Главный рабочий цикл:
        1. Сохранение вопроса.
        2. Получение ответа от ИИ (база в это время свободна).
        3. Сохранение ответа.
        """

        # 1. Сохраняем сообщение пользователя (Транзакция 1: зашли-вышли)
        await self.message_repo.add_message(chat_id, role="user", content=content)

        # 2. Вызываем LLM (Тут может быть долгое ожидание, БД не занята!)
        rag_result = await get_llm_answer(content)
        assistant_response = rag_result["answer"]
        sources = rag_result.get("sources", [])
        print(rag_result)
        # 3. Сохраняем ответ ассистента (Транзакция 2: зашли-вышли)
        await self.message_repo.add_message(chat_id, role="assistant", content=assistant_response,sources = sources)

        return {
            "response": assistant_response,
            "sources": sources
        }