from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from dotenv import load_dotenv
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

# Настройки текстового разделителя
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=[r"\n\n\n", r"\n\n", r"\n", r".\s", r"!\s", r"?\s", r"\s", ""],
    length_function=len
)