import datetime
import os
import sqlite3
from typing import Any, Dict, List, Optional

from app.config import *

from .base import DataBase


class DataBaseManager(DataBase):
    """Работа с базой данных SQL_Lite"""

    def __init__(self, db_path: Optional[str] = None):
        """Инициализация менеджера базы данных SQLite.

        Args:
            db_path (Optional[str]): Путь к файлу базы данных.
                Если не указан, используется путь по умолчанию.
        """
        if db_path:
            self.db_name = db_path
        else:
            # Используем путь из конфигурации или путь по умолчанию
            self.db_name = os.getenv("DATABASE_PATH", "./storage/db_chat/tables.db")

        # Создаем директорию если её нет
        os.makedirs(os.path.dirname(self.db_name), exist_ok=True)

        check_table = self._check_table()
        if not check_table:
            self._create_table_chats_and_messages()

    def _check_table(self) -> bool:
        """Проверка на наличие базовых таблиц"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                # Проверяем существование таблицы chats
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    ("chats",),
                )
                chat_table = cursor.fetchone()

                # Проверяем существование таблицы messages
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    ("messages",),
                )
                messages_table = cursor.fetchone()

                # Возвращаем True только если обе таблицы существуют
                return chat_table is not None and messages_table is not None
        except sqlite3.Error as e:
            print(f"Ошибка при проверке таблиц: {e}")
            return False

    def _create_table_chats_and_messages(self) -> None:
        """Creates tables chats and messages"""
        create_query_chats = """CREATE TABLE IF NOT EXISTS chats 
                          ( chat_id TEXT NOT NULL, 
                            user_id TEXT NOT NULL,
                            title TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            PRIMARY KEY (chat_id)          
                          )"""
        create_query_messages = """CREATE TABLE IF NOT EXISTS messages 
                          ( id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT, 
                            chat_id TEXT NOT NULL REFERENCES chats(chat_id) ON DELETE CASCADE,
                            role TEXT NOT NULL,
                            content TEXT NOT NULL,
                            created_at TEXT NOT NULL
                          )"""

        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor.execute(create_query_chats)
            cursor.execute(create_query_messages)

    def add_new_chat(self, chat_id: str, user_id: str, title: str) -> bool:
        """Добавление нового чата в базу данных."""
        try:
            create_query_chats = """INSERT INTO chats (chat_id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)"""

            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    create_query_chats,
                    (
                        chat_id,
                        user_id,
                        title,
                        datetime.datetime.now().isoformat(),
                        datetime.datetime.now().isoformat(),
                    ),
                )
                return True
        except sqlite3.Error as e:
            print(f"Ошибка при добавлении чата: {e}")
            return False

    def get_all_chats(self, user_id: str) -> List[Dict[str, Any]]:
        """Получение списка всех чатов пользователя."""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT chat_id, title, created_at, updated_at FROM chats WHERE user_id=?",
                    (user_id,),
                )
                chats = cursor.fetchall()

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

    def get_chat(self, chat_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Получение информации о конкретном чате."""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT chat_id, title, created_at, updated_at FROM chats WHERE chat_id=? AND user_id=?",
                    (chat_id, user_id),
                )
                chat = cursor.fetchone()

                if chat:
                    return {
                        "chat_id": chat[0],
                        "title": chat[1],
                        "created_at": chat[2],
                        "updated_at": chat[3],
                    }
                return None
        except sqlite3.Error as e:
            print(f"Ошибка при получении чата: {e}")
            return None

    def update_chat_title(self, chat_id: str, user_id: str, new_title: str) -> bool:
        """Обновление заголовка чата."""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE chats SET title=?, updated_at=? WHERE chat_id=? AND user_id=?",
                    (new_title, datetime.datetime.now().isoformat(), chat_id, user_id),
                )
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении заголовка чата: {e}")
            return False

    def delete_chat(self, chat_id: str, user_id: str) -> bool:
        """Удаление чата и всех связанных сообщений."""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM chats WHERE chat_id=? AND user_id=?",
                    (chat_id, user_id),
                )
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Ошибка при удалении чата: {e}")
            return False

    def add_new_message(self, chat_id: str, role: str, content: str) -> bool:
        """Добавление нового сообщения в бд."""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                add_query_messages = """INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)"""
                cursor.execute(
                    add_query_messages,
                    (chat_id, role, content, datetime.datetime.now().isoformat()),
                )
                return True
        except sqlite3.Error as e:
            print(f"Ошибка при добавлении сообщения: {e}")
            return False

    def get_chat_messages(
        self, chat_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Получение истории сообщений чата."""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                if limit:
                    cursor.execute(
                        "SELECT id, role, content, created_at FROM messages WHERE chat_id=? ORDER BY created_at ASC LIMIT ?",
                        (chat_id, limit),
                    )
                else:
                    cursor.execute(
                        "SELECT id, role, content, created_at FROM messages WHERE chat_id=? ORDER BY created_at ASC",
                        (chat_id,),
                    )
                messages = cursor.fetchall()

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
        except sqlite3.Error as e:
            print(f"Ошибка при получении сообщений: {e}")
            return []

    def delete_message(self, message_id: int, chat_id: str) -> bool:
        """Удаление конкретного сообщения."""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM messages WHERE id=? AND chat_id=?",
                    (message_id, chat_id),
                )
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Ошибка при удалении сообщения: {e}")
            return False


if __name__ == "__main__":
    db = DataBaseManager()
    # Пример использования
    # db.add_new_chat("test_chat_1", "user_1", "Тестовый чат")
    # chats = db.get_all_chats("user_1")
    # print(f"Чаты: {chats}")
