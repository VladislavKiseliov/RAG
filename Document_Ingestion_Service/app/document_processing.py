import sys
from pathlib import Path
from typing import List, Dict, Any

import camelot
import pandas as pd
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

# --- Импорт нашего файла конфигурации (Placeholders) ---
# Для работы в вашей среде убедитесь, что app.config импортирует text_splitter
# и необходимые алиасы типов.
from .config import text_splitter
import os
from dotenv import load_dotenv

load_dotenv()

# Пути и директории (с возможностью переопределить через .env)
TOKEN_HF = os.getenv("HF_TOKEN")
# Проверка, что токен существует (рекомендуется)
if not TOKEN_HF:
    raise ValueError("HUGGINGFACEHUB_API_TOKEN не найден в переменных окружения.")

# --- Тип для возврата табличных данных ---
# Таблица: {"page": str, "table": str (JSON-строка)}
TableData = List[Dict[str, str]]

_EMBEDDINGS_CACHE: HuggingFaceEmbeddings | None = None


def ingest_document(file_path: str | Path, embeddings: HuggingFaceEmbeddings, collection_name: str) -> Dict[str, Any] | None:
    """Обрабатывает один PDF-файл и возвращает payload и векторы."""
    try:
        row_data_chunks = extract_text_from_pdf(file_path)

        chunk_texts = [chunk.page_content for chunk in row_data_chunks["chunks"]]
        vectors: List[List[float]] = generate_embeddings(embeddings, chunk_texts)
        if not vectors:
            return None

        payloads = []
        for chunk in row_data_chunks["chunks"]:
            payloads.append({
                "row_text": chunk.page_content,
                "metadata": chunk.metadata,
            })

        return {
            "collection_name": collection_name,
            "payload": payloads,
            "vector": vectors
        }

    except Exception as e:
        print(f"❌ Ошибка при загрузке PDF: {e}")
        return None


def initialization_embeddings_model():
    """Инициализирует модель для генерации эмбеддингов текста.

        Использует предобученную модель BAAI/bge-m3 с нормализацией векторов
        (критично для косинусного поиска).

        Returns:
            HuggingFaceEmbeddings: Настроенная модель эмбеддингов, либо None
                при ошибке инициализации.
    """

    global _EMBEDDINGS_CACHE
    if _EMBEDDINGS_CACHE is not None:
        return _EMBEDDINGS_CACHE

    try:
        embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            encode_kwargs={'normalize_embeddings': True},
        )
        print("✅ Локальная модель эмбеддингов настроена.")
        _EMBEDDINGS_CACHE = embeddings
        return _EMBEDDINGS_CACHE
    except Exception as e:
        print(f"❌ Ошибка настройки HuggingFaceEmbeddings: {e}")
        return None

def generate_embeddings(embeddings: HuggingFaceEmbeddings,texts: List[str]) -> List[List[float]]:
    """Генерирует эмбеддинги для списка текстов.

        Передаёт батч текстов в модель и возвращает список векторных представлений.

        Args:
            embeddings_model: Настроенная модель HuggingFaceEmbeddings.
            texts: Список строк (текстов) для векторизации.

        Returns:
            Список векторов (каждый — список float). При ошибке — пустой список.

        Example:
            >>> vectors = generate_embeddings(embeddings, ["текст 1", "текст 2"])
            >>> len(vectors)  # 2
            >>> len(vectors[0])  # например, 1024 (размерность модели)
        """
    try:
        return embeddings.embed_documents(texts)
    except Exception as e:
        print(f"❌ Ошибка при кодировании вектора: {e}")
        return []


def find_pdf_files(directory: str) -> List[Path]:
    """Находит все PDF‑файлы в указанной директории.

    Рекурсия не используется — ищет только в указанной папке.

    Args:
        directory: Путь к директории (str или Path).

    Returns:
        Список объектов Path, соответствующих PDF‑файлам.
    """

    path = Path(directory)
    return [f for f in path.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]


def extract_text_from_pdf(file_path: Path) -> Dict[str, List[Document]]:
    """Извлекает и разбивает текст из PDF‑файла.

    Загружает PDF, парсит страницы, разбивает на чанки согласно text_splitter
    из конфигурации.

    Args:
        file_path: Путь к PDF‑файлу (str или Path).

    Returns:
        Словарь с ключами:
        - "chunks": список объектов Document (разбитые чанки);
        - "pages": список объектов Document (целые страницы).

    Side effects:
        - При успешной обработке выводит количество чанков.
        - При ошибке возвращает пустые списки и выводит сообщение.

    Example:
        >>> result = extract_text_from_pdf("doc.pdf")
        >>> chuncks = result["chunks"]
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    try:
        loader = PyPDFLoader(str(file_path))
        pages: List[Document] = loader.load()
        split_docs: List[Document] = text_splitter.split_documents(pages)


        print(f"📄 Обработано и разбито {len(split_docs)} чанков из {file_path}")
        print(f"🎉 Всего чанков готово к индексации: {len(split_docs)}")
        return {"chunks": split_docs, "pages": pages}


    except Exception as e:

        print(f"❌ Ошибка при чтении или разбиении PDF {file_path}: {e}")

        return {"chunks": [], "pages": []}





def extract_tables_from_pdf(file_path: str) -> TableData:
    """Извлекает таблицы из PDF с помощью Camelot.

    Для каждой таблицы возвращает номер страницы и JSON‑строку с данными.

    Args:
        file_path: Путь к PDF‑файлу.

    Returns:
        Список словарей с ключами:
        - "page": номер страницы (строка);
        - "table_json": JSON‑строка с данными таблицы (orient="records").

    Side effects:
        - Выводит количество найденных таблиц.
        - Пропускает таблицы с точностью <50% или пустые.
    """

    result: TableData = []
    print(file_path)
    try:
        # Указываем pages="all" или "1-end" для обработки всего документа
        tables = camelot.read_pdf(
            filepath=file_path,
            pages="1-end",
            flavor="lattice",
            flag_size=True,
            # Дополнительный параметр для лучшей обработки пустых ячеек (полезно для RAG)
            strip_text='\n'
        )

        print(f"✅ Найдено {len(tables)} таблиц в документе.")

        for table in tables:
            # Проверка на качество извлечения и пустые таблицы
            if table.df.empty or table.parsing_report.get('accuracy', 0) < 50:
                print(f"⚠️ Пропущена таблица со страницы {table.page} из-за низкой точности/пустоты.")
                continue

            # 1. Получаем JSON-строку из DataFrame
            # orient="records" - для списка объектов (удобно для LLM)
            # force_ascii=False - для читаемой кириллицы (UTF-8)
            json_table_str: str = table.df.to_json(orient="records", force_ascii=False)

            # 2. Получаем номер страницы (возвращается как строка)
            page_num_str: str = table.page

            # 3. Собираем результат
            result.append({"page": page_num_str, "table_json": json_table_str})

    except FileNotFoundError:
        print(f"❌ Файл не найден: {file_path}")
    except Exception as e:
        print(f"❌ Непредвиденная ошибка при извлечении таблиц: {e}")

    return result




