from pathlib import Path
from langchain.text_splitter import RecursiveCharacterTextSplitter


# Пути
DIRECTORY_DOCS = r"C:\Users\RGG\Desktop\RagProgramm\docs"
QDRANT_PATH = "./qdrant_storage"
COLLECTION_NAME = "rag_documents_collection"


# Настройки чанков
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# --- НАСТРОЙКА ПОЛЬЗОВАТЕЛЬСКОГО РУССКОГО ПРОМПТА RAG ---

# Модели

# EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
LLM_MODEL_NAME = "gemini-1.5-flash-latest"


text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[r"\n\n\n", r"\n\n", r"\n", r".\s", r"!\s", r"?\s", r"\s", ""],
        length_function=len
    )