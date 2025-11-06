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

    def __init__(self,DATABASE_URL:Optional[str]="sqlite:///../storage/db_chat/alchemy.db"):
        self.DATABASE_URL = DATABASE_URL
        self.engine = create_engine(self.DATABASE_URL,echo=True)
        self.SessionLocal = sessionmaker(bind=self.engine)


    def add_new_chat(self, chat_id: str, user_id: str, title: str) -> bool:
        """Добавление нового чата в базу данных."""

        with self.SessionLocal() as session:
            with session.begin():
                chats = Chats(chat_id=chat_id, user_id=user_id, title=title)
                session.add(chats)



    def get_all_chats(self, user_id: str) -> List[Dict[str, Any]]:
        """Получение списка всех чатов пользователя."""
        try:
            with self.SessionLocal() as session:
                stmt = select(Chats).filter_by(user_id=user_id)
                chats = session.scalars(stmt).all()

                result = []
                for chat in chats:
                    result.append(
                        {
                            "chat_id": chat[0],
                            "title": chat[1],
                            "created_at": chat[2],
                            "updated_at": chat[3],
                        }
                    )
                return result
        except sqlite3.Error as e:
            print(f"Ошибка при получении чатов: {e}")
            return []

    def update_chat_title(self, chat_id: str, user_id: str, new_title: str) -> bool:
        """Обновление заголовка чата."""
        try:
            with self.SessionLocal() as session:
                chat = session.get(Chats, chat_id,user_id)
                chat.title = new_title
                chat.updated_at = datetime.utcnow()
                session.commit()

                return session.rowcount > 0

        except sqlite3.Error as e:
            print(f"Ошибка при обновлении заголовка чата: {e}")
            return False

    def delete_chat(self, chat_id: str, user_id: str) -> bool:
        """Удаление чата и всех связанных сообщений."""
        try:
            with self.SessionLocal() as session:
                chat = session.get(Chats, chat_id,user_id)
                session.delete(chat)
                session.commit()

                return session.rowcount > 0

        except sqlite3.Error as e:
            print(f"Ошибка при удалении чата: {e}")
            return False

    def add_new_message(self, chat_id: str, role: str, content: str) -> bool:
        """Добавление нового сообщения в бд."""
        try:
            with self.SessionLocal() as session:
                message = Messages(chat_id=chat_id, role=role, content=content)
                session.add(message)
                session.commit()

                return True
        except sqlalchemy.exc.PendingRollbackError as e:#Транзакция завершилась неудачно и должна быть откатана перед продолжением.
            print(f"Ошибка при получении сообщений: {e}")
            return []



    def get_chat_messages(
            self, chat_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Получение истории сообщений чата."""
        try:
            with self.SessionLocal() as session:

                stmt = (
                    select(Messages)
                    .filter_by(chat_id=chat_id)
                    .order_by(Messages.created_at.desc())
                    .limit(limit or None)
                )

                messages = session.scalars(stmt).all()

                result = []
                for message in messages:
                    result.append(
                        {
                            "id": message[0],
                            "role": message[1],
                            "content": message[2],
                            "created_at": message[3],
                        }
                    )
                return result
        except sqlalchemy.exc.NoResultFound as e: #Требовалось получить результат из базы данных, но он не был найден.
            print(f"Ошибка при получении сообщений: {e}")
            return []
        except sqlalchemy.exc.NoSuchTableError as e: #Таблица не существует или не видна для соединения.
            print(f"Ошибка при получении сообщений: {e}")
            return []

    def delete_message(self, message_id: int, chat_id: str) -> bool:
        """Удаление конкретного сообщения."""
        try:
            with self.SessionLocal() as session:

                message = session.get(Chats, chat_id, message_id)
                session.delete(message)
                session.commit()

                return session.rowcount > 0
        except sqlite3.Error as e:
            print(f"Ошибка при удалении сообщения: {e}")
            return False

    def add_new_user(self):
        with self.SessionLocal() as session:
            new_user = Users(chat_id=123, login="john", password="")
            session.add_all([new_user])
            session.commit()

    def get_new_user(self):
        with self.SessionLocal() as session:
            user = session.get(Users, 1)
            print(user.login)






# Запуск
if __name__ == "__main__":
    Db = Data_Base_Alchemy("sqlite:///../../storage/db_chat/alchemy.db")
    Db.add_new_chat(chat_id=134543543,user_id=123,title='testnew')
    # Db.add_new_user()
    #create_table()
    #add_new_user()
    # get_new_user()
    # add_new_chat(chat_id='123',user_id="43254",title="test")



