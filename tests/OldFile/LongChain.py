from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pypdf
from pathlib import Path
from typing import List, Dict
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
import os

file_path = r"/docs/12.pdf"

# --- ИСПОЛЬЗУЕМ ЛОКАЛЬНУЮ МОДЕЛЬ ЭМБЕДДИНГОВ Hugging Face ---
# Эта модель будет скачана и запущена на вашем компьютере,
# поэтому проблем с квотой API не будет.
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

# Инициализируем семантический разделитель с локальной моделью
text_splitter = SemanticChunker(embedding_model)

# Загружаем PDF и получаем список объектов Document
loader = PyPDFLoader(file_path)
documents = loader.lazy_load()

# Извлекаем текстовый контент из каждого документа
page_texts = [doc.page_content for doc in documents]

# Разбиваем текст на семантические чанки
semantic_chunks = text_splitter.create_documents(page_texts)

for i, doc in enumerate(semantic_chunks):
    print(f"--- ЧАНК {i+1} ---")
    print(doc.page_content)






















# Функция для загрузки и разбиения PDF
def load_and_split_pdf_semantic(file_path: Path) -> List[Dict]:
    """
    Читает PDF и выполняет умную семантическую разбивку на чанки.
    """
    chunks = []
    try:
        reader = pypdf.PdfReader(file_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n\n"

        # Инициализация умного разделителя
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # Оптимальный размер чанка, можно настроить
            chunk_overlap=200,  # Небольшое перекрытие для сохранения контекста
            length_function=len,
            is_separator_regex=False
        )

        # Разбиваем текст на чанки
        texts = text_splitter.create_documents([full_text])

        # Создаем список словарей с метаданными
        for i, doc in enumerate(texts):
            chunks.append({
                "text": doc.page_content,
                "source": file_path.name,
                "page": i + 1  # Здесь может потребоваться более сложная логика для определения страницы
            })

    except Exception as e:
        print(f"❌ Ошибка при чтении PDF {file_path.name}: {e}")
    return chunks


# Пример использования

# pdf_file = Path(file_patch)
# smart_chunks = load_and_split_pdf_semantic(pdf_file)
# print(f"Создано {len(smart_chunks)} семантических чанков.")
#
#
# loader = PyPDFLoader(file_patch)
# pages = []
# for page in loader.lazy_load():
#     pages.append(page)
#
# print(f"{pages[0].metadata}\n")
# print(pages[0].page_content)
