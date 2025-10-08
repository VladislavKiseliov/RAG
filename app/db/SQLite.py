import datetime
import os
import sqlite3
from typing import Any, Dict, List

from app.config import *

class DataBaseManager:
    """Работа с базой данных SQL_Lite"""

    def __init__(self):
        # self.db_name = SQLITE
        self.db_name = r"C:\Users\RGG\Desktop\RagProgramm\storage\db_chat\tables.db"
        check_table = self._check_table()
        if not check_table:
            self._create_table_chats_and_messages()


    def _check_table(self):
        """Проверка на наличие базовых таблиц"""
        try:
            with sqlite3.connect(self.db_name) as conn:
                cursor = conn.cursor()
                # Проверяем существование таблицы chats
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", ('chats',))
                chat_table = cursor.fetchone()

                # Проверяем существование таблицы messages
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", ('messages',))
                messages_table = cursor.fetchone()

                # Возвращаем True только если обе таблицы существуют
                return chat_table is not None and messages_table is not None
        except sqlite3.Error as e:
            print(f"Ошибка при проверке таблиц: {e}")
            return False

    def _create_table_chats_and_messages(self):
        """Creates tables chats and messages"""

        create_query_chats = """CREATE TABLE IF NOT EXISTS chats 
                          ( chat_id TEXT NOT NULL, 
                            user_id TEXT NOT NULL,
                            title TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            PRIMARY KEY (chat_id)          
                          )"""
        create_query_massages = """CREATE TABLE IF NOT EXISTS messages 
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
            cursor.execute(create_query_massages)

    def add_new_chat(self, chat_id: str, user_id: str, title: str):

        create_query_chats = """INSERT INTO chats (chat_id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)"""

        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(create_query_chats, (chat_id, user_id, title, datetime.datetime.now(), datetime.datetime.now()))

    def check_chats(self):
        """Проверка существующих чатов в базе"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chats")
            chats = cursor.fetchall()
            print(f"{chats=}")

    def check_messages(self,chat_id: str):

        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages WHERE chat_id=?", (chat_id,))
            messages = cursor.fetchall()
            print(f"{messages=}")

    def add_new_message(self, id: str,chat_id: str, role: str, content: str):

        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            add_query_messanges = """INSERT INTO messages (id,chat_id,role,content,reated_at) VALUES (?,?,?,?,?)"""
            cursor.execute(add_query_messanges, (chat_id, role, content, datetime.datetime.now()))


if __name__ == "__main__":
    db = DataBaseManager()
    db.check_chats()
    db.check_messages(chat_id=1759839633685)
















