#!/usr/bin/env python3
"""Тестирование интерфейса базы данных."""

import os
import sys
import tempfile

# Добавляем корневую директорию проекта в путь поиска модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.db.base_db import DataBase
from app.db.SQLite import DataBaseManager


def test_database_interface():
    """Тестирование соответствия интерфейса."""
    # Создаем временную базу данных для тестирования
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        # Создаем экземпляр реализации
        db: DataBase = DataBaseManager(db_path)
        
        # Проверяем, что все абстрактные методы реализованы
        # Это автоматически проверяется Python при создании экземпляра
        
        # Тестируем основные методы
        print("Тестирование базы данных...")
        
        # Добавляем тестовый чат
        result = db.add_new_chat("test_chat_1", "user_1", "Тестовый чат")
        print(f"Добавление чата: {'Успешно' if result else 'Ошибка'}")
        
        # Получаем все чаты пользователя
        chats = db.get_all_chats("user_1")
        print(f"Получено чатов: {len(chats)}")
        
        if chats:
            chat = chats[0]
            print(f"Первый чат: {chat}")
            
            # Обновляем заголовок чата
            result = db.update_chat_title(chat["chat_id"], "user_1", "Обновленный заголовок")
            print(f"Обновление заголовка: {'Успешно' if result else 'Ошибка'}")
            
            # Добавляем сообщения
            result1 = db.add_new_message(chat["chat_id"], "user", "Привет, как дела?")
            result2 = db.add_new_message(chat["chat_id"], "assistant", "Привет! У меня всё хорошо, спасибо!")
            print(f"Добавление сообщений: {'Успешно' if result1 and result2 else 'Ошибка'}")
            
            # Получаем сообщения
            messages = db.get_chat_messages(chat["chat_id"])
            print(f"Получено сообщений: {len(messages)}")
            for msg in messages:
                print(f"  {msg['role']}: {msg['content']}")
        
        print("Тестирование завершено успешно!")
        
    except Exception as e:
        print(f"Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Удаляем временный файл
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    test_database_interface()