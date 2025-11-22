import asyncio
import sqlite3
from typing import List, Dict, Any, Optional

import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker
from sqlalchemy import String, Integer, ForeignKey, DateTime, create_engine, select, BigInteger
from datetime import datetime
from app.db.interfaces.base_db import DataBase
from app.models.database_models import Chats,Messages,Users


class Data_Base_Alchemy():

    def add_new_chat(self, db: Session,chat_id: str, user_id: str, title: str) -> bool:
        """Добавление нового чата в базу данных."""
        try:
            # 1. Используем переданную активную сессию 'db'
            chats = Chats(chat_id=chat_id, user_id=user_id, title=title)
            db.add(chats)

            # 2. Явно фиксируем транзакцию (commit)
            db.commit()
            return True

        except Exception as e:
            # Если произошла ошибка, откатываем изменения в этой сессии
            db.rollback()
            print(f"Ошибка при добавлении чата: {e}")
            return False

    def get_all_chats(self, db: Session, user_id: str) -> List[Dict[str, Any]]:
        """Получение списка всех чатов пользователя."""
        try:
            # Используем переданную сессию 'db'
            stmt = select(Chats).filter_by(user_id=user_id)
            chats = db.scalars(stmt).all()

            result = []
            for chat in chats:
                # Исправлено: доступ к атрибутам ORM (chat.attribute) вместо сырых индексов (chat[0])
                result.append(
                    {
                        "chat_id": chat.chat_id,
                        "title": chat.title,
                        "created_at": chat.created_at,
                        "updated_at": chat.updated_at,
                    }
                )
            return result
        except Exception as e:
            # Если это SELECT, rollback не требуется, но лучше его добавить
            # для безопасности, если это часть более крупной транзакции
            print(f"Ошибка при получении чатов: {e}")
            return []

    def update_chat_title(self, db: Session, chat_id: str, user_id: str, new_title: str) -> bool:
        """Обновление заголовка чата."""
        try:
            # Используем переданную сессию 'db'
            chat = db.get(Chats, (chat_id, user_id))  # Используйте кортеж для составного PK

            if not chat:
                return False

            chat.title = new_title
            chat.updated_at = datetime.utcnow()
            db.commit()  # Фиксируем изменения

            return True  # Возвращаем True, если коммит успешен

        except Exception as e:
            db.rollback()  # Откат транзакции при ошибке
            print(f"Ошибка при обновлении заголовка чата: {e}")
            return False

    def delete_chat(self, db: Session, chat_id: str, user_id: str) -> bool:
        """Удаление чата и всех связанных сообщений."""
        try:
            chat = db.get(Chats, (chat_id, user_id))  # Используйте кортеж для составного PK

            if not chat:
                return False

            db.delete(chat)
            db.commit()

            return True

        except Exception as e:
            db.rollback()
            print(f"Ошибка при удалении чата: {e}")
            return False

    # --- Функции для работы с сообщениями ---

    def add_new_message(self, db: Session, chat_id: str, role: str, content: str) -> bool:
        """Добавление нового сообщения в бд."""
        try:
            message = Messages(chat_id=chat_id, role=role, content=content)
            db.add(message)
            db.commit()  # Фиксируем

            return True
        except Exception as e:  # Общий Exception вместо PendingRollbackError
            db.rollback()  # Откат транзакции
            print(f"Ошибка при добавлении сообщения: {e}")
            return False

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
                # Исправлено: доступ к атрибутам ORM
                result.append(
                    {
                        "id": message.id,
                        "role": message.role,
                        "content": message.content,
                        "created_at": message.created_at,
                    }
                )
            return result
        except Exception as e:
            print(f"Ошибка при получении сообщений: {e}")
            return []

    def delete_message(self, db: Session, message_id: int, chat_id: str) -> bool:
        """Удаление конкретного сообщения."""
        try:
            # Предполагаем, что message_id - это уникальный PK для Messages
            # Если Chat_id не является частью PK сообщения, ищите по ID сообщения
            message = db.get(Messages, message_id)

            if not message:
                return False

            db.delete(message)
            db.commit()

            return True
        except Exception as e:
            db.rollback()
            print(f"Ошибка при удалении сообщения: {e}")
            return False

    # --- Функции для работы с пользователями ---

    def add_new_user(self, db: Session, login: str, password: str):
        # Добавили login и password в аргументы для практичности
        try:
            new_user = Users(chat_id = 123,login=login, password=password)  # Удалена жестко заданная 'chat_id'
            db.add(new_user)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Ошибка при добавлении пользователя: {e}")

    def get_user(self, db: Session, user_name: str) -> Optional[Users]:
        try:
            user = db.get(Users, user_name)
            return user
        except Exception as e:
            print(e)

    def get_user_by_id(self, db: Session, user_name: str):
        # Переименована для соответствия цели
        stmt = select(Users).where(Users.login == user_name)
        user = db.scalars(stmt).first()
        return user






# Запуск
if __name__ == "__main__":
    Db = Data_Base_Alchemy("sqlite:///../../../storage/db_chat/alchemy.db")
    # Db.add_new_chat(chat_id=134543543,user_id=123,title='testnew')
    Db.add_new_user()
    #create_table()
    #add_new_user()
    # get_new_user()
    # add_new_chat(chat_id='123',user_id="43254",title="test")



