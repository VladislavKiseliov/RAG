from pathlib import Path
# Стало: Импорт из отдельного пакета для Text Splitters
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
from dotenv import load_dotenv
# # Этот импорт, вероятно, верен, так как SemanticChunker - экспериментальный модуль
# from langchain_experimental.text_splitter import SemanticChunker

load_dotenv()

# Пути и директории (с возможностью переопределить через .env)
DIRECTORY_DOCS = os.getenv("DOCS_DIRECTORY", "./docs")
QDRANT_PATH = os.getenv("QDRANT_PATH", "./qdrant_storage")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "rag_documents_collection")

# Настройки RAG (константы)
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
SIMILARITY_THRESHOLD = 0.5
MAX_RESULTS = 5

# Модели
EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
LLM_MODEL_NAME = 'models/gemini-2.5-flash'

# # Настройки текстового разделителя
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=[r"\n\n\n", r"\n\n", r"\n", r".\s", r"!\s", r"?\s", r"\s", ""],
    length_function=len
)
# P-Chunk: Разбиение по целым параграфам
parent_splitter = RecursiveCharacterTextSplitter(
    # В приоритете – двойной перенос (новый параграф), затем одиночный
    separators=["\n\n", "\n"],
    chunk_size=3000,
    chunk_overlap=250
)
# C-Chunk: Разбиение по пунктам и подпунктам
child_splitter = RecursiveCharacterTextSplitter(
    # Приоритет: Маркеры списков, чтобы сохранить пункт целиком
    separators=["\n- ", "\n• ", "\n1. ", "\n"],
    chunk_size=500,
    chunk_overlap=100
)

