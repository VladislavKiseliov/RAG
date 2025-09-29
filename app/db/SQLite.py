import datetime
import os
import sqlite3
from typing import Any, Dict, List

from app.config import *

class DataBaseManager:
    """Работа с базой данных SQL_Lite"""
    def __init__(self):
        self.db_name = SQLITE
        self._create_table_chats_and_messages()


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
        curent_datetime = datetime.datetime.now()
        print("233333333")
        # create_query_chats = f"""INSERT INTO chats ({chat_id}, {user_id}, {title}, {curent_datetime})"""
        # with sqlite3.connect(self.db_name) as conn:
        #     cursor = conn.cursor()
        #     cursor.execute(create_query_chats)


    def _check_exist_table(self, table_name: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM "Initial_Data" WHERE table_name = ? LIMIT 1',
                (table_name,)
            )
            return cursor.fetchone() is not None

    def _create_table_query(self, table_name: str, colums: List[str]) -> str:
        """Create a request to create a table in the database"""
        # Проверяем, что колонки не пустые
        if not colums:
            self.logger.error("Список колонок пуст!")
            raise ValueError("Колонки не определены")
        # Формируем SQL-запрос для создания таблицы

        create_table_query = f"""
            CREATE TABLE IF NOT EXISTS '{table_name}' (
                {", ".join([f"{col} REAL" for col in colums])}  
            )
        """
        self.logger.debug(f"SQL-запрос создания таблицы: {create_table_query} _create_table_query")
        return create_table_query

    def _insert_query(self, table_name: str, colums: List[str]) -> str:
        """Create a request to insert data into the table"""
        insert_query = f"""
            INSERT INTO '{table_name}' ({", ".join(colums)}) 
            VALUES ({", ".join(["?"] * len(colums))})
        """
        self.logger.debug(f"SQL-запрос вставки данных: {insert_query}")
        return insert_query


















