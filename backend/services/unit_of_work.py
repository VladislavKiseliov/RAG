from backend.repository.chat_repository import ChatRepository
from backend.repository.messages_repository import MessageRepository
from backend.repository.auth_repository import AuthRepository
from backend.repository.messenger_repository import MessengerRepository
from backend.repository.note_repository import NoteRepository


class UnitOfWork:
    def __init__(self, session_factory):
        self._sf = session_factory


    async def __aenter__(self):
        self._session = self._sf()  # одна сессия
        return self

    @property
    def messages(self):
        return MessageRepository(self._session)

    @property
    def chats(self):
        return ChatRepository(self._session)

    @property
    def auth(self):
        return AuthRepository(self._session)

    @property
    def messenger(self):
        return MessengerRepository(self._session)

    @property
    def notes(self):
        return NoteRepository(self._session)

    async def commit(self):
        await self._session.commit()  # коммитит ВСЁ разом

    async def rollback(self):
        await self._session.rollback()  # откатывает ВСЁ разом

    async def refresh(self, obj, attribute_names=None):
        await self._session.refresh(obj, attribute_names=attribute_names)

    async def __aexit__(self, exc_type, *args):
        if exc_type:
            await self.rollback()
        await self._session.close()