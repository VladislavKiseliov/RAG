import os
from pathlib import Path
from langchain_community.vectorstores import Qdrant as LangChainQdrant
from app.core.document_processing import list_pdf_files, load_and_split_pdf


class QdrantManager:
    """Управление векторной базой данных Qdrant"""

    def __init__(self, embeddings, collection_name, qdrant_path):
        self.collection_name = collection_name
        self.qdrant_path = qdrant_path
        self.embeddings = embeddings

    def check_collection_exists(self):
        """Проверка существования коллекции Qdrant"""
        is_indexed = os.path.exists(self.qdrant_path) and len(list(Path(self.qdrant_path).glob('*'))) > 0
        return is_indexed

    def load_collection(self):
        """Загрузка существующей коллекции"""
        if not self.check_collection_exists():
            raise FileNotFoundError("Коллекция не существует. Сначала создайте коллекцию.")

        qdrant_db = LangChainQdrant.from_existing_collection(
            embedding=self.embeddings,
            collection_name=self.collection_name,
            path=self.qdrant_path
        )
        return qdrant_db

    def create_collection_from_documents(self, docs_directory):
        """Создание новой коллекции из документов в указанной директории"""
        # Получаем список PDF файлов
        list_files = list_pdf_files(docs_directory)

        # Собираем все документы
        all_docs = []
        for file_path in list_files:
            docs = load_and_split_pdf(file_path)
            if docs:
                all_docs.extend(docs)

        if not all_docs:
            raise ValueError("Документы для индексации не найдены.")

        # Создаем коллекцию из документов
        qdrant_db = LangChainQdrant.from_documents(
            all_docs,
            self.embeddings,
            path=self.qdrant_path,
            collection_name=self.collection_name
        )

        print(f"🎉 Qdrant база знаний, содержащая {len(all_docs)} чанков, создана в {self.qdrant_path}")
        return qdrant_db

    def get_or_create_collection(self, docs_directory):
        """Получение существующей коллекции или создание новой"""
        if self.check_collection_exists():
            print("✅ Qdrant коллекция найдена. Загружаем...")
            return self.load_collection()
        else:
            print("🆕 Коллекция Qdrant не найдена. Создаем и индексируем документы...")
            return self.create_collection_from_documents(docs_directory)

    def get_retriever(self, docs_directory):
        """Создание retriever для поиска по коллекции"""
        if self.embeddings is None:
            raise ValueError("Эмбеддинги не настроены. Невозможно создать ретривер.")

        # Получаем или создаем коллекцию
        qdrant_db = self.get_or_create_collection(docs_directory)

        # Создаем retriever
        retriever = qdrant_db.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={
                "k": 5,
                "score_threshold": 0.5
            }
        )
        return retriever