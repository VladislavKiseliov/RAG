from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class DataBase(ABC):
    """Абстрактный класс для работы с базой данных чатов и сообщений.
    
    Определяет интерфейс для всех реализаций хранилища данных.
    Реализации должны обеспечивать:
    - Хранение информации о чатах
    - Хранение истории сообщений
    - Целостность данных
    - Обработку ошибок
    """
    
    # === Инициализация и проверка структуры ===
    
    @abstractmethod
    def _check_table(self) -> bool:
        """Проверка наличия необходимых таблиц в базе данных.
        
        Выполняется при инициализации для проверки корректности структуры БД.
        
        Returns:
            bool: True если все необходимые таблицы существуют, False если нет
            
        Raises:
            DatabaseError: Если произошла ошибка при подключении к базе данных
        """
        pass
    
    @abstractmethod
    def _create_table_chats_and_messages(self) -> None:
        """Создание таблиц для хранения чатов и сообщений.
        
        Создает необходимую структуру таблиц если они не существуют.
        Таблицы:
        - chats: информация о чатах
        - messages: история сообщений
        
        Raises:
            DatabaseError: Если произошла ошибка при создании таблиц
        """
        pass
    
    # === Работа с чатами ===
    
    @abstractmethod
    def add_new_chat(self, chat_id: str, user_id: str, title: str) -> bool:
        """Добавление нового чата в базу данных.
        
        Args:
            chat_id (str): Уникальный идентификатор чата
            user_id (str): Идентификатор пользователя-владельца чата
            title (str): Заголовок или название чата
            
        Returns:
            bool: True если чат успешно добавлен, False в случае ошибки
            
        Raises:
            DatabaseError: Если произошла ошибка при работе с базой данных
            ValueError: Если переданы некорректные параметры
        """
        pass
    
    @abstractmethod
    def get_all_chats(self, user_id: str) -> List[Dict[str, Any]]:
        """Получение списка всех чатов пользователя.
        
        Args:
            user_id (str): Идентификатор пользователя
            
        Returns:
            List[Dict[str, Any]]: Список словарей с информацией о чатах.
                Каждый словарь содержит ключи: chat_id, title, created_at, updated_at
                
        Raises:
            DatabaseError: Если произошла ошибка при работе с базой данных
        """
        pass
    
    @abstractmethod
    def get_chat(self, chat_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Получение информации о конкретном чате.
        
        Args:
            chat_id (str): Идентификатор чата
            user_id (str): Идентификатор пользователя (для проверки доступа)
            
        Returns:
            Optional[Dict[str, Any]]: Словарь с информацией о чате или None если чат не найден
            
        Raises:
            DatabaseError: Если произошла ошибка при работе с базой данных
        """
        pass
    
    @abstractmethod
    def update_chat_title(self, chat_id: str, user_id: str, new_title: str) -> bool:
        """Обновление заголовка чата.
        
        Args:
            chat_id (str): Идентификатор чата
            user_id (str): Идентификатор пользователя (для проверки доступа)
            new_title (str): Новый заголовок чата
            
        Returns:
            bool: True если заголовок успешно обновлен, False в случае ошибки
            
        Raises:
            DatabaseError: Если произошла ошибка при работе с базой данных
            ValueError: Если переданы некорректные параметры
        """
        pass
    
    @abstractmethod
    def delete_chat(self, chat_id: str, user_id: str) -> bool:
        """Удаление чата и всех связанных сообщений.
        
        Args:
            chat_id (str): Идентификатор чата для удаления
            user_id (str): Идентификатор пользователя (для проверки доступа)
            
        Returns:
            bool: True если чат успешно удален, False в случае ошибки
            
        Raises:
            DatabaseError: Если произошла ошибка при работе с базой данных
        """
        pass
    
    # === Работа с сообщениями ===
    
    @abstractmethod
    def add_new_message(self, chat_id: str, role: str, content: str) -> bool:
        """Добавление нового сообщения в чат.
        
        Args:
            chat_id (str): Идентификатор чата
            role (str): Роль отправителя ("user" или "assistant")
            content (str): Текст сообщения
            
        Returns:
            bool: True если сообщение успешно добавлено, False в случае ошибки
            
        Raises:
            DatabaseError: Если произошла ошибка при работе с базой данных
            ValueError: Если переданы некорректные параметры
        """
        pass
    
    @abstractmethod
    def get_chat_messages(self, chat_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Получение истории сообщений чата.
        
        Args:
            chat_id (str): Идентификатор чата
            limit (Optional[int]): Максимальное количество сообщений (None для всех)
            
        Returns:
            List[Dict[str, Any]]: Список словарей с сообщениями.
                Каждый словарь содержит ключи: id, role, content, created_at
                
        Raises:
            DatabaseError: Если произошла ошибка при работе с базой данных
        """
        pass
    
    @abstractmethod
    def delete_message(self, message_id: int, chat_id: str) -> bool:
        """Удаление конкретного сообщения.
        
        Args:
            message_id (int): Идентификатор сообщения
            chat_id (str): Идентификатор чата (для проверки доступа)
            
        Returns:
            bool: True если сообщение успешно удалено, False в случае ошибки
            
        Raises:
            DatabaseError: Если произошла ошибка при работе с базой данных
        """
        pass