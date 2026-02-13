import os

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

DIRECTORY_DOCS = os.getenv("DOCS_DIRECTORY", "./docs")
QDRANT_PATH = os.getenv("QDRANT_PATH", "./qdrant_storage")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "rag_documents_collection")

HF_TOKEN = os.getenv("HF_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

HTTP_PROXY = os.getenv("HTTP_PROXY", "")
HTTPS_PROXY = os.getenv("HTTPS_PROXY", "")
NO_PROXY = os.getenv("NO_PROXY", "")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
SIMILARITY_THRESHOLD = 0.5
MAX_RESULTS = 5

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "models/gemini-2.5-flash-lite")

if HTTP_PROXY:
    os.environ["HTTP_PROXY"] = HTTP_PROXY
    os.environ["http_proxy"] = HTTP_PROXY
if HTTPS_PROXY:
    os.environ["HTTPS_PROXY"] = HTTPS_PROXY
    os.environ["https_proxy"] = HTTPS_PROXY
if NO_PROXY:
    os.environ["NO_PROXY"] = NO_PROXY
    os.environ["no_proxy"] = NO_PROXY

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=[r"\n\n\n", r"\n\n", r"\n", r".\s", r"!\s", r"?\s", r"\s", ""],
    length_function=len,
)

parent_splitter = RecursiveCharacterTextSplitter(
    separators=["\n\n", "\n"],
    chunk_size=3000,
    chunk_overlap=250,
)

child_splitter = RecursiveCharacterTextSplitter(
    separators=["\n- ", "\n* ", "\n1. ", "\n"],
    chunk_size=500,
    chunk_overlap=100,
)
