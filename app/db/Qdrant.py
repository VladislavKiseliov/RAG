import os
from pathlib import Path
from typing import Any, List

from langchain.schema import Document
from langchain_community.vectorstores import Qdrant as LangChainQdrant

from app.config import SIMILARITY_THRESHOLD, MAX_RESULTS
from app.core.document_processing import list_pdf_files, load_and_split_pdf
from app.db.base_vector_db import VectorDBInterface


class QdrantManager(VectorDBInterface):
    """Управление векторной базой данных Qdrant"""

    def __init__(
        self,
        embeddings,
        collection_name,
        qdrant_path,
        docs_directory= None,
        search_k=None,
        score_threshold=None,
    ):
        self.collection_name = collection_name
        self.qdrant_path = qdrant_path
        self.embeddings = embeddings
        self.docs_directory = docs_directory
        # Используем переданные параметры или значения по умолчанию из конфига
        self.search_k = search_k if search_k is not None else MAX_RESULTS
        self.score_threshold = (
            score_threshold if score_threshold is not None else SIMILARITY_THRESHOLD
        )

    def _check_collection_exists(self)-> bool:
        """Проверка существования коллекции Qdrant"""
        is_indexed = (
            os.path.exists(self.qdrant_path)
            and len(list(Path(self.qdrant_path).glob("*"))) > 0
        )
        return is_indexed

    def _load_collection(self) -> Any:
        """Загрузка существующей коллекции"""
        try:
            qdrant_db = LangChainQdrant.from_existing_collection(
                embedding=self.embeddings,
                collection_name=self.collection_name,
                path=self.qdrant_path,
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                "Коллекция не существует. Сначала создайте коллекцию."
            )
        except ValueError:
            raise ValueError("Проверь: имя коллекции, путь, embedding-модель")
        except Exception as e:
            if "collection not found" in str(e).lower():
                raise Exception(
                    f"❌ Коллекция '{self.collection_name}' не найдена в базе"
                )
            elif "corrupted" in str(e).lower():
                raise Exception("❌ База данных повреждена. Удали папку и пересоздай")
            else:
                raise Exception(
                    f"❌ Неизвестная ошибка при загрузке Qdrant: {type(e).__name__}: {e}"
                )
        return qdrant_db


    def _split_documents(self,docs_directory):
        """Создание новой коллекции из документов в указанной директории (для обратной совместимости)"""
        # Получаем список PDF файлов
        list_files = list_pdf_files(docs_directory)

        # Собираем все документы
        all_chunks = []
        for file_path in list_files:
            docs = load_and_split_pdf(file_path)
            if docs:
                all_chunks.extend(docs)

        if not all_chunks:
            raise ValueError("Документы для индексации не найдены.")

        return all_chunks

    def _create_collection_from_documents(self, documents: List[Document]) -> Any:
        """Создание новой коллекции из списка документов"""

        # Создаем коллекцию из документов
        qdrant_db = LangChainQdrant.from_documents(
            documents,
            self.embeddings,
            path=self.qdrant_path,
            collection_name=self.collection_name,
        )

        print(
            f"🎉 Qdrant база знаний, содержащая {len(documents)} чанков, создана в {self.qdrant_path}"
        )
        return qdrant_db

    def _get_or_create_collection(self) -> Any:
        """Получение существующей коллекции или создание новой"""
        if self.check_collection_exists():
            print("✅ Qdrant коллекция найдена. Загружаем...")
            return self._load_collection()
        else:
            print("🆕 Коллекция Qdrant не найдена. Создаем и индексируем документы...")
            all_chunks = self._split_documents(self.docs_directory)
            return self._create_collection_from_documents(all_chunks)

    def get_retriever(self, search_kwargs=None) -> Any:
        """Создание retriever для поиска по коллекции"""
        if self.embeddings is None:
            raise ValueError("Эмбеддинги не настроены. Невозможно создать ретривер.")

        qdrant_db = self._get_or_create_collection()

        # Используем переданные параметры поиска или значения по умолчанию
        if search_kwargs is None:
            search_kwargs = {
                "k": self.search_k,
                "score_threshold": self.score_threshold,
            }

        # Создаем retriever
        retriever = qdrant_db.as_retriever(
            search_type="similarity_score_threshold", search_kwargs=search_kwargs
        )
        return retriever

    def similarity_search(self, query: str, k: int = 5, **kwargs) -> List[Document]:
        """Поиск документов, семантически похожих на запрос"""
        # Для реализации этого метода нам нужно получить векторную базу данных
        # Поскольку у нас нет прямого доступа к ней, мы можем использовать retriever
        # Но для простоты реализации просто загрузим коллекцию и выполним поиск
        try:
            qdrant_db = self.load_collection()
            return qdrant_db.similarity_search(query, k=k, **kwargs)
        except Exception as e:
            raise Exception(f"Ошибка при выполнении поиска: {str(e)}")