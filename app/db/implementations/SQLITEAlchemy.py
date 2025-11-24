import asyncio
import sqlite3
from typing import List, Dict, Any, Optional
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker
from sqlalchemy import String, Integer, ForeignKey, DateTime, create_engine, select, BigInteger
from datetime import datetime
from app.db.interfaces.base_db import DataBase
from app.models.database_models import Chats,Messages,Users


class Data_Base_Alchemy(DataBase):
    """Реализация интерфейса базы данных с использованием SQLAlchemy ORM."""

    def add_new_chat(self, db: Session, chat_id: str, user_id: str, title: str) -> bool:
        """Добавление нового чата в базу данных."""
        try:
            chats = Chats(chat_id=chat_id, user_id=user_id, title=title)
            db.add(chats)
            db.commit()
            return True

        except IntegrityError:
            db.rollback()
            raise Exception("Chat already exists")
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when adding chat: {str(e)}")

    def get_all_chats(self, db: Session, user_id: str) -> List[Dict[str, Any]]:
        """Получение списка всех чатов пользователя."""
        try:
            stmt = select(Chats).filter_by(user_id=user_id)
            chats = db.scalars(stmt).all()

            result = []
            for chat in chats:
                result.append(
                    {
                        "chat_id": chat.chat_id,
                        "title": chat.title,
                        "created_at": chat.created_at,
                        "updated_at": chat.updated_at,
                    }
                )
            return result
        except SQLAlchemyError as e:
            raise Exception(f"Database error when getting chats: {str(e)}")

    def update_chat_title(self, db: Session, chat_id: str, user_id: str, new_title: str) -> bool:
        """Обновление заголовка чата."""
        try:
            chat = db.get(Chats, (chat_id, user_id))

            if not chat:
                return False

            chat.title = new_title
            chat.updated_at = datetime.utcnow()
            db.commit()

            return True

        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when updating chat title: {str(e)}")

    def delete_chat(self, db: Session, chat_id: str, user_id: str) -> bool:
        """Удаление чата и всех связанных сообщений."""
        try:
            chat = db.get(Chats, (chat_id, user_id))

            if not chat:
                return False

            db.delete(chat)
            db.commit()

            return True

        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when deleting chat: {str(e)}")

    # --- Функции для работы с сообщениями ---

    def add_new_message(self, db: Session, chat_id: str, role: str, content: str) -> bool:
        """Добавление нового сообщения в бд."""
        try:
            message = Messages(chat_id=chat_id, role=role, content=content)
            db.add(message)
            db.commit()
            return True
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when adding message: {str(e)}")

    def get_chat_messages(
            self, db: Session, chat_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Получение истории сообщений чата."""
        try:
            stmt = (
                select(Messages)
                .filter_by(chat_id=chat_id)
                .order_by(Messages.created_at.desc())
                .limit(limit or None)
            )

            messages = db.scalars(stmt).all()

            result = []
            for message in messages:
                result.append(
                    {
                        "id": message.id,
                        "role": message.role,
                        "content": message.content,
                        "created_at": message.created_at,
                    }
                )
            return result
        except SQLAlchemyError as e:
            raise Exception(f"Database error when getting messages: {str(e)}")

    def delete_message(self, db: Session, message_id: int, chat_id: str) -> bool:
        """Удаление конкретного сообщения."""
        try:
            message = db.get(Messages, message_id)

            if not message:
                return False

            db.delete(message)
            db.commit()

            return True
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when deleting message: {str(e)}")

    # --- Функции для работы с пользователями ---

    def add_new_user(self, db: Session, login: str, password: str):
        """Добавление нового пользователя в базу данных."""
        try:
            new_user = Users(chat_id = 123,login=login, password=password)
            db.add(new_user)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise Exception("User with this login already exists")
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when adding user: {str(e)}")

    def get_user(self, db: Session, user_name: str) -> Optional[Users]:
        """Получение пользователя по имени."""
        try:
            user = db.get(Users, user_name)
            return user
        except SQLAlchemyError as e:
            raise Exception(f"Database error when getting user: {str(e)}")

    def get_user_by_login(self, db: Session, user_name: str):
        """Получение пользователя по логину."""
        try:
            stmt = select(Users).where(Users.login == user_name)
            user = db.scalars(stmt).first()
            return user
        except SQLAlchemyError as e:
            raise Exception(f"Database error when getting user by login: {str(e)}")