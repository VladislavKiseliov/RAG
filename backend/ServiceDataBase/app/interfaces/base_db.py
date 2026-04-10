from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session


class DataBase(ABC):
    """Абстрактный класс для работы с базой данных чатов и сообщений.
    
    Определяет интерфейс для всех реализаций хранилища данных.
    Реализации должны обеспечивать:
    - Хранение информации о чатах
    - Хранение истории сообщений
    - Целостность данных
    - Обработку ошибок
    """
    
    # === Работа с чатами ===
    
    @abstractmethod
    def add_new_chat(self, db: Session, chat_id: str, user_id: str, title: str) -> bool:
        """Добавление нового чата в базу данных.
        
        Args:
           db (Session): Сессия SQLAlchemy
            chat_id (str): Уникальный идентификатор чата
            user_id (str): Идентификатор пользователя-владельца чата
            title (str): Заголовок или название чата
            
        Returns:
            bool: True если чат успешно добавлен, False в случае ошибки
        """
        pass
    
    @abstractmethod
    def get_all_chats(self, db: Session, user_id: str) -> List[Dict[str, Any]]:
        """Получение списка всех чатов пользователя.
        
        Args:
           db (Session): Сессия SQLAlchemy
            user_id (str): Идентификатор пользователя
            
        Returns:
            List[Dict[str, Any]]: Список словарей с информацией о чатах.
                Каждый словарь содержит ключи: chat_id, title, created_at, updated_at
        """
        pass
    
    @abstractmethod
    def update_chat_title(self, db: Session, chat_id: str, user_id: str, new_title: str) -> bool:
        """Обновление заголовка чата.
        
        Args:
           db (Session): Сессия SQLAlchemy
            chat_id (str): Идентификатор чата
            user_id (str): Идентификатор пользователя (для проверки доступа)
            new_title (str): Новый заголовок чата
            
        Returns:
            bool: True если заголовок успешно обновлен, False в случае ошибки
        """
        pass
    
    @abstractmethod
    def delete_chat(self, db: Session, chat_id: str, user_id: str) -> bool:
        """Удаление чата и всех связанных сообщений.
        
        Args:
           db (Session): Сессия SQLAlchemy
            chat_id (str): Идентификатор чата для удаления
            user_id (str): Идентификатор пользователя (для проверки доступа)
            
        Returns:
            bool: True если чат успешно удален, False в случае ошибки
        """
        pass
    
    # === Работа с сообщениями ===
    
    @abstractmethod
    def add_new_message(self, db: Session, chat_id: str, role: str, content: str) -> bool:
        """Добавление нового сообщения в чат.
        
        Args:
           db (Session): Сессия SQLAlchemy
            chat_id (str): Идентификатор чата
            role (str): Роль отправителя ("user" или "assistant")
            content (str): Текст сообщения
            
        Returns:
            bool: True если сообщение успешно добавлено, False в случае ошибки
        """
        pass
    
    @abstractmethod
    def get_chat_messages(self, db: Session, chat_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Получение истории сообщений чата.
        
        Args:
           db (Session): Сессия SQLAlchemy
            chat_id (str): Идентификатор чата
            limit (Optional[int]): Максимальное количество сообщений (None для всех)
            
        Returns:
            List[Dict[str, Any]]: Список словарей с сообщениями.
                Каждый словарь содержит ключи: id, role, content, created_at
        """
        pass
    
    @abstractmethod
    def delete_message(self, db: Session, message_id: int, chat_id: str) -> bool:
        """Удаление конкретного сообщения.
        
        Args:
           db (Session): Сессия SQLAlchemy
            message_id (int): Идентификатор сообщения
            chat_id (str): Идентификатор чата (для проверки доступа)
            
        Returns:
            bool: True если сообщение успешно удалено, False в случае ошибки
        """
        pass
    
    # === Работа с пользователями ===
    
    @abstractmethod
    def add_new_user(self, db: Session, login: str, password: str) -> None:
        """Добавление нового пользователя в базу данных.
        
        Args:
           db (Session): Сессия SQLAlchemy
            login (str): Логин пользователя
            password (str): Пароль пользователя
        """
        pass
    
    @abstractmethod
    def get_user(self, db: Session, user_name: str) -> Optional[Any]:
        """Получение пользователя по имени.
        
        Args:
           db (Session): Сессия SQLAlchemy
            user_name (str): Имя пользователя
            
        Returns:
            Optional[Any]: Объект пользователя или None если не найден
        """
        pass
    
    @abstractmethod
    def get_user_by_login(self, db: Session, user_name: str) -> Optional[Any]:
        """Получение пользователя по логину.
        
        Args:
           db (Session): Сессия SQLAlchemy
            user_name (str): Логин пользователя
            
        Returns:
            Optional[Any]: Объект пользователя или None если не найден
        """
        pass