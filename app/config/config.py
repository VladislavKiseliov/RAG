from pathlib import Path
# Стало: Импорт из отдельного пакета для Text Splitters
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
from dotenv import load_dotenv
# Этот импорт, вероятно, верен, так как SemanticChunker - экспериментальный модуль
from langchain_experimental.text_splitter import SemanticChunker

load_dotenv()

# Пути и директории (с возможностью переопределить через .env)
DIRECTORY_DOCS = os.getenv("DOCS_DIRECTORY", "./docs")
QDRANT_PATH = os.getenv("QDRANT_PATH", "./qdrant_storage")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "rag_documents_collection")
SQLITE = os.getenv("SQLITE", ".storage/db_chat/tables.db")

# Настройки RAG (константы)
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
SIMILARITY_THRESHOLD = 0.5
MAX_RESULTS = 5

# Модели
EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
LLM_MODEL_NAME = 'models/gemini-2.5-flash'

# # Настройки текстового разделителя
# text_splitter = RecursiveCharacterTextSplitter(
#     chunk_size=CHUNK_SIZE,
#     chunk_overlap=CHUNK_OVERLAP,
#     separators=[r"\n\n\n", r"\n\n", r"\n", r".\s", r"!\s", r"?\s", r"\s", ""],
#     length_function=len
# )


from langchain_huggingface import HuggingFaceEmbeddings # Используйте модель из вашего файла

# 1. Инициализация модели эмбеддингов
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2") # Пример

# 2. Инициализация SemanticChunker
# В качестве разделителя используется 'sentence'
text_splitter = SemanticChunker(embeddings)

# # 3. Разбиение текста
# long_text = "Ваш очень длинный текст с разными темами..."
# semantic_chunks = text_splitter.split_text(long_text)