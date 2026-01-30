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


def ingest_documents(directory: str, embeddings: HuggingFaceEmbeddings, collection_name: str)->Dict[str, Any] | None:
    """Основной конвейер инжеста документов в векторную БД.

        1. Находит все PDF в директории.
        2. Извлекает и разбивает текст.
        3. Генерирует эмбеддинги.
        4. Формирует payload для загрузки.

        Args:
            directory: Путь к папке с PDF‑файлами.
            embeddings_model: Настроенная модель для эмбеддингов.
            collection_name: Имя коллекции в векторной БД.

        Returns:
            Словарь с ключами:
            - "collection_name": имя коллекции;
            - "payload": список словарей с "row_text" и "metadata";
            - "vector": список векторных представлений.
            При ошибке — None.
    """
    try:
        paths_documents = find_pdf_files(directory)
        payloads = []
        all_vectors = []

        for file_path in paths_documents:
            print(f"Обработка файла: {file_path}")
            row_data_chunks = extract_text_from_pdf(file_path)

            # 1. Собираем тексты всех чанков
            chunk_texts = [chunk.page_content for chunk in row_data_chunks["chunks"]]

            # 2. ПАКЕТНАЯ ВЕКТОРИЗАЦИЯ (для всех собранных чанков сразу)
            vectors:List[List[float]] = generate_embeddings(embeddings, chunk_texts)
            if not vectors:  # если векторизация провалилась
                continue

            # 3. Накапливаем векторы
            all_vectors.extend(vectors)

            # 4. Формируем payload (синхронно с векторами)
            for i, chunk in enumerate(row_data_chunks["chunks"]):
                payloads.append({
                    "row_text": chunk.page_content,
                    "metadata": chunk.metadata,
                })

        return {
            "collection_name": collection_name,
            "payload": payloads,
            "vector": all_vectors
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

        # --- Блок отладки (сохранение содержимого) ---
        with open('output1234.txt', 'w', encoding='utf-8') as f:
            for i, doc in enumerate(split_docs, 1):
                f.write(f"Исходная страница {i}:\n")
                f.write(f"{doc.page_content.strip()}\n")
                f.write(f"Метаданные {doc.metadata=}")
                # В PyPDFLoader 'page' уже является номером страницы (0-based)
                # print(f"📄 Страница (1-based): {doc.metadata.get('page', 0) + 1}\n")
                f.write("-" * 50 + "\n\n")

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




if __name__ == "__main__":
    # Исправляем путь для работы с Path (желательно) или str
    pdf_path_str = "../test/12.pdf"
    # pdf_path_obj = Path(pdf_path_str)
    #
    # # Загрузка и разбиение текста
    list_file = extract_text_from_pdf(pdf_path_str)

    # Извлечение таблиц
    # tables_data = get_table_pdf(pdf_path_str)
    # string = ["Положения настоящего стандарта обязательны для применения структурными подразделениями, дочерними обществами и организациями ОАО «Газпром».","СТО Газпром 1.2-2009 Система стандартизации ОАО «Газпром». Планы разработки документов по техническому регулированию в ОАО «Газпром». Порядок формирования, утверждения и реализации"]
    # embend = initialization_embenddings_model()
    # res = create_embeddings_vector(embend,string)
    # with open ('output123.txt', 'w', encoding='utf-8') as f:
    #     f.write(str(res))
    # # print(res)
    # your_single_vector = res[0]
    # print(len(your_single_vector),len(res[1]))
    # print(len(res))
    res = main(r"C:\Users\RGG\Desktop\RagProgramm\Document_Ingestion_Service\app","test")
    with open('outputTets.txt', 'w', encoding='utf-8') as f:

        for i in range(len(res["payload"])):
            f.write(str(res["payload"][i]) + "\n")
            f.write(str(res["vector"][i]) + "\n")
            print(len(res["vector"][i]))
            f.write("\n")

    # print("\n--- Результат извлечения таблиц ---")
    # if tables_data:
    #     for item in tables_data:
    #         print(f"Найдена таблица со страницы: {item['page']}")
    #         # Для краткости выводим только первые 100 символов JSON
    #         print(f"JSON (фрагмент): {item['table_json'][:100]}...")
    #
    # # print(sys.path)
