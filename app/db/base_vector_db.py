from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain.schema import Document


class VectorDBInterface(ABC):
    """Абстрактный класс для работы с векторной базой данных.

    Определяет интерфейс для всех реализаций векторных хранилищ.
    Реализации должны обеспечивать:
    - Хранение векторных представлений документов
    - Семантический поиск по векторам
    - Управление коллекциями документов
    """

    @abstractmethod
    def _check_collection_exists(self) -> bool:
        """Проверка существования коллекции векторов.

        Returns:
            bool: True если коллекция существует, False если нет
        """
        pass

    @abstractmethod
    def _load_collection(self) -> Any:
        """Загрузка существующей коллекции векторов.

        Returns:
            Объект векторной базы данных

        Raises:
            Exception: Если коллекция не существует или повреждена
        """
        pass

    @abstractmethod
    def _create_collection_from_documents(self, documents: List[Document]) -> Any:
        """Создание новой коллекции из списка документов.

        Args:
            documents (List[Document]): Список документов для индексации

        Returns:
            Объект векторной базы данных

        Raises:
            ValueError: Если список документов пуст
            Exception: При ошибках создания коллекции
        """
        pass

    @abstractmethod
    def _get_or_create_collection(self) -> Any:
        """Получение существующей коллекции или создание новой.

        Returns:
            Объект векторной базы данных
        """
        pass

    @abstractmethod
    def get_retriever(self, search_kwargs: Optional[Dict[str, Any]] = None) -> Any:
        """Создание ретривера для поиска по коллекции.

        Args:
            search_kwargs (Optional[Dict[str, Any]]): Параметры поиска

        Returns:
            Объект ретривера для использования в цепочках LangChain

        Raises:
            ValueError: Если эмбеддинги не настроены
        """
        pass

    @abstractmethod
    def similarity_search(self, query: str, k: int = 5, **kwargs) -> List[Document]:
        """Поиск документов, семантически похожих на запрос.

        Args:
            query (str): Текстовый запрос для поиска
            k (int): Количество возвращаемых документов
            **kwargs: Дополнительные параметры поиска

        Returns:
            List[Document]: Список релевантных документов

        Raises:
            Exception: При ошибках поиска
        """
        pass