import enum
from typing import List, Optional
import uuid
from datetime import datetime, timezone


from sqlalchemy import select, update, delete, Select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.models.database_models import Chats, Messages, Users, RefreshTokens
from rag_service import DocumentAlreadyExists
from rag_service.models import Documents

class DocumentAlreadyExists(Exception):
    """Брошено при конфликте уникальности по file_hash."""
    def __init__(self, file_hash: str) -> None:
        super().__init__(f"Document with hash '{file_hash}' already exists")
        self.file_hash = file_hash

class DocumentStatus(str, enum.Enum):
    processing = "processing"
    completed = "completed"
    error = "error"



class BaseRepository:
    """Базовый класс для инъекции фабрики сессий."""
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

class AuthRepository(BaseRepository):
    """Репозиторий для управления доступом и сессиями (Refresh-токены)."""

    async def create_user(self, login: str, hashed_password: str) -> Users:
        """
        Регистрирует нового пользователя.
        :param login: Уникальный логин пользователя.
        :param hashed_password: Хешированный пароль.
        :return: Объект созданного пользователя.
        """
        async with self.session_factory() as session:
            async with session.begin():
                new_user = Users(login=login, password=hashed_password)
                session.add(new_user)
            await session.refresh(new_user)
            return new_user

    async def get_user_by_login(self, login: str) -> Optional[Users]:
        """
        Поиск пользователя по логину.
        :param login: Строка логина.
        :return: Объект Users или None.
        """
        async with self.session_factory() as session:
            stmt = select(Users).where(Users.login == login)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def add_refresh_token(self, user_id: uuid.UUID, token: str, expires_at: datetime) -> None:
        """
        Сохраняет новый Refresh-токен для пользователя.
        :param user_id: ID пользователя.
        :param token: Строка токена.
        :param expires_at: Время истечения.
        """
        async with self.session_factory() as session:
            async with session.begin():
                refresh = RefreshTokens(
                    user_id=user_id,
                    token=token,
                    expires_at=expires_at,
                    revoked=False
                )
                session.add(refresh)

    async def get_refresh_token(self, token: str) -> Optional[RefreshTokens]:
        """Поиск токена в базе для проверки его валидности."""
        async with self.session_factory() as session:
            stmt = select(RefreshTokens).where(RefreshTokens.token == token)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> int:
        """Отзывает все активные токены пользователя (например, при смене пароля)."""
        async with self.session_factory() as session:
            async with session.begin():
                stmt = (
                    update(RefreshTokens)
                    .where(RefreshTokens.user_id == user_id, RefreshTokens.revoked == False)
                    .values(revoked=True)
                )
                result = await session.execute(stmt)
                return result.rowcount

    async def revoke_refresh_token(self, token: str) -> bool:
        """Деактивирует конкретный токен (выход из системы)."""
        async with self.session_factory() as session:
            async with session.begin():
                stmt = (update(RefreshTokens).where(RefreshTokens.token == token).values(revoked=True))
                result = await session.execute(stmt)
                return result.rowcount > 0

    async def get_user_id(self, user_id: uuid.UUID) -> Optional[Users]:
        """Проверка существования пользователя по ID."""
        async with self.session_factory() as session:
            stmt = select(Users).where(Users.id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()


class UserRepository(BaseRepository):
    """Управление данными профиля пользователя."""

    async def get_user_by_login(self, login: str) -> Optional[Users]:
        async with self.session_factory() as session:
            stmt = select(Users).where(Users.login == login)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[Users]:
        async with self.session_factory() as session:
            stmt = select(Users).where(Users.id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def delete_user(self, user_id: uuid.UUID) -> bool:
        async with self.session_factory() as session:
            async with session.begin():
                stmt = delete(Users).where(Users.id == user_id)
                result = await session.execute(stmt)
            return result.rowcount > 0

    async def get_users(self, page_size: int = 50) -> list[Users]:
        async with self.session_factory() as session:
            stmt = select(Users).limit(page_size)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def create_user(self, login: str, password: str) -> Users:
        async with self.session_factory() as session:
            async with session.begin():
                user = Users(login=login, password=password)
                session.add(user)
            await session.refresh(user)
            return user

    async def update_user(self, user_id: uuid.UUID, new_login: str, new_password: str) -> bool:
        async with self.session_factory() as session:
            async with session.begin():
                stmt = (
                    update(Users)
                    .where(Users.id == user_id)
                    .values(login=new_login, password=new_password, updated_at=datetime.now(timezone.utc))
                )
                result = await session.execute(stmt)
            return result.rowcount > 0




class ChatRepository(BaseRepository):
    """Управление чатами (создание, переименование, удаление)."""

    async def create_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID, title: str) -> Chats:
        """Создает новую сессию чата."""
        async with self.session_factory() as session:
            async with session.begin():
                chat = Chats(chat_id=chat_id, user_id=user_id, title=title)
                session.add(chat)
            await session.refresh(chat)
            return chat

    async def get_all_chats(self, user_id: uuid.UUID) -> List[Chats]:
        """Список всех чатов пользователя, отсортированный по дате обновления."""
        async with self.session_factory() as session:
            stmt = select(Chats).where(Chats.user_id == user_id).order_by(Chats.updated_at.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def delete_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Удаление чата (доступно только владельцу)."""
        async with self.session_factory() as session:
            async with session.begin():
                stmt = delete(Chats).where(Chats.chat_id == chat_id, Chats.user_id == user_id)
                result = await session.execute(stmt)
                return result.rowcount > 0

    async def update_chat_title(self, chat_id: uuid.UUID, user_id: uuid.UUID, new_title: str) -> bool:
        """Обновление заголовка чата."""
        async with self.session_factory() as session:
            async with session.begin():
                stmt = (
                    update(Chats)
                    .where(Chats.chat_id == chat_id, Chats.user_id == user_id)
                    .values(title=new_title, updated_at=datetime.now())
                )
                result = await session.execute(stmt)
                return result.rowcount > 0

class MessageRepository(BaseRepository):
    """Работа с сообщениями внутри чатов."""

    async def add_message(self, chat_id: uuid.UUID, role: str, content: str,sources :list = None) -> Messages:
        """Сохранение нового сообщения (от пользователя или AI)."""
        async with self.session_factory() as session:
            async with session.begin():
                message = Messages(chat_id=chat_id, role=role, content=content,sources = sources)
                session.add(message)
            await session.refresh(message)
            return message

    async def get_history(self, chat_id: uuid.UUID, limit: int = 50) -> List[Messages]:
        """Получение истории сообщений для контекста LLM."""
        async with self.session_factory() as session:
            stmt = (
                select(Messages)
                .where(Messages.chat_id == chat_id)
                .order_by(Messages.created_at.asc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())



class DocumentRepository(BaseRepository):

    async def get_document_by_hash(self, file_hash: str) -> Documents | None:
        """Return a document by SHA-256 hash, or `None` if absent."""
        async with self.session_factory() as session:
            result = await session.execute(select(Documents).where(Documents.file_hash == file_hash))
            return result.scalar_one_or_none()

    async def get_document_by_id(self, doc_id: uuid.UUID) -> Documents | None:
        """Return a document by UUID, or `None` if absent."""
        async with self.session_factory() as session:
            result = await session.execute(select(Documents).where(Documents.id == doc_id))
            return result.scalar_one_or_none()

    async def list_documents(
            self,
            *,
            limit: int,
            offset: int,
            status: str | None = None,
            filename: str | None = None,
            created_from: datetime | None = None,
            created_to: datetime | None = None,
    ) -> list[Documents]:
        """List documents with pagination and optional filters."""
        query: Select = select(Documents)

        if status:
            query = query.where(Documents.status == status)
        if filename:
            query = query.where(Documents.filename.ilike(f"%{filename}%"))
        if created_from is not None:
            query = query.where(Documents.created_at >= created_from)
        if created_to is not None:
            query = query.where(Documents.created_at <= created_to)

        query = query.order_by(Documents.created_at.desc()).limit(limit).offset(offset)

        async with self.session_factory() as session:
            result = await session.execute(query)
            return list(result.scalars().all())

    async def create_document(
            self,
            filename: str,
            file_hash: str,
            meta: dict | None,
            *,
            doc_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Create a document in `processing` status and return its id."""
        doc = Documents(
            id=doc_id or uuid.uuid4(),
            filename=filename,
            file_hash=file_hash,
            meta=meta,
            status=DocumentStatus.processing,
        )

        async with self.session_factory() as session:
            try:
                session.add(doc)
                await session.flush()
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                message = str(exc)
                if (
                        "uq_documents_file_hash" in message
                        or ("duplicate key value" in message and "file_hash" in message)
                ):
                    raise DocumentAlreadyExists(file_hash) from exc
                raise

        return doc.id

    async def set_status(
            self,
            doc_id: uuid.UUID,
            status: DocumentStatus,
            *,
            chunk_count: int | None = None,
    ) -> None:
        """Update document status and optionally its processed child chunk count."""
        values: dict[str, DocumentStatus | int] = {"status": status}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count

        async with self.session_factory() as session:
            await session.execute(update(Documents).where(Documents.id == doc_id).values(**values))
            await session.commit()

    async def delete_document(self, doc_id: uuid.UUID) -> None:
        """Delete document row; linked parent chunks are removed by cascade."""
        async with self.session_factory() as session:
            await session.execute(delete(Documents).where(Documents.id == doc_id))
            await session.commit()