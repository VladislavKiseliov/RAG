import os
from pathlib import Path
from typing import List
import numpy as np

# --- Загрузка переменных окружения ---
from dotenv import load_dotenv
load_dotenv()  # загружает переменные из .env

# --- Импорты LangChain и компонентов ---
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Qdrant
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import RetrievalQA
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from sentence_transformers import SentenceTransformer

# --- Импорт наших файлов ---
from app.config import *



def list_pdf_files(directory: str) -> List[Path]:
    """Возвращает список PDF-файлов."""
    path = Path(directory)
    return [f for f in path.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]


def load_and_split_pdf(file_path) -> List[Document]:
    """
    Разбивает PDF-файл и возвращает список объектов LangChain Document.
    """


    try:
        loader = PyPDFLoader(str(file_path))
        pages = loader.load()

        split_docs = text_splitter.split_documents(pages)

        with open('output.txt', 'w', encoding='utf-8') as f:
            for i, doc in enumerate(split_docs, 1):
                f.write(f"Чанк {i}:\n")
                f.write(f"{doc.page_content.strip()}\n")
                page_num = doc.metadata.get('page')
                display_page = page_num + 1 if isinstance(page_num, int) else 'N/A'
                f.write(f"📄 Страница: {display_page}\n")
                f.write("-" * 50 + "\n\n")


        print(f"📄 Обработано и разбито {len(split_docs)} чанков из {file_path}")

    except Exception as e:
        print(f"❌ Ошибка при чтении или разбиении PDF {file_path}: {e}")

    print(f"🎉 Всего чанков готово к индексации: {len(split_docs)}")

    return split_docs


if __name__ == "__main__":
    list_file = load_and_split_pdf(r"C:\Users\RGG\Desktop\RagProgramm\docs\123.pdf")
    print(list_file)