import sys
from pathlib import Path
from typing import List, Dict, Any

import camelot
import pandas as pd
from camelot.core import TableList  # Добавляем импорт для корректного тайп-хинта
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

# --- Импорт нашего файла конфигурации (Placeholders) ---
# Для работы в вашей среде убедитесь, что app.config импортирует text_splitter
# и необходимые алиасы типов.
try:
    from app.config import text_splitter
except ImportError:
    # Заглушка, если app/config.py не существует в текущей структуре
    print("Внимание: 'text_splitter' не импортирован из 'app.config'. Используется заглушка.")
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

# --- Тип для возврата табличных данных ---
# Таблица: {"page": str, "table": str (JSON-строка)}
TableData = List[Dict[str, str]]


def list_pdf_files(directory: str) -> List[Path]:
    """Возвращает список PDF-файлов."""
    path = Path(directory)
    return [f for f in path.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]


def load_and_split_pdf(file_path: Path) -> Dict[str, List[Document]]:
    """
    Разбивает PDF-файл и возвращает список объектов LangChain Document.
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    try:
        loader = PyPDFLoader(str(file_path))
        pages: List[Document] = loader.load()
        split_docs: List[Document] = text_splitter.split_documents(pages)

        # --- Блок отладки (сохранение содержимого) ---
        with open('output123.txt', 'w', encoding='utf-8') as f:
            for i, doc in enumerate(pages, 1):
                f.write(f"Исходная страница {i}:\n")
                f.write(f"{doc.page_content.strip()}\n")
                # В PyPDFLoader 'page' уже является номером страницы (0-based)
                # print(f"📄 Страница (1-based): {doc.metadata.get('page', 0) + 1}\n")
                f.write("-" * 50 + "\n\n")

        print(f"📄 Обработано и разбито {len(split_docs)} чанков из {file_path}")

    except Exception as e:
        print(f"❌ Ошибка при чтении или разбиении PDF {file_path}: {e}")
        return {"chunks": [], "pages": []}

    print(f"🎉 Всего чанков готово к индексации: {len(split_docs)}")
    return {"chunks": split_docs, "pages": pages}


def get_table_pdf(file_path: str) -> TableData:
    """
    Извлекает таблицы из PDF с использованием Camelot и возвращает их в виде списка
    JSON-строк, с указанием номера страницы.
    """
    result: TableData = []
    try:
        # Указываем pages="all" или "1-end" для обработки всего документа
        tables: TableList = camelot.read_pdf(
            file_path=file_path,
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
    pdf_path_str = r"C:\Users\RGG\Desktop\RagProgramm\docs\123.pdf"
    pdf_path_obj = Path(pdf_path_str)

    # Загрузка и разбиение текста
    list_file = load_and_split_pdf(pdf_path_obj)

    # Извлечение таблиц
    tables_data = get_table_pdf(pdf_path_str)

    print("\n--- Результат извлечения таблиц ---")
    if tables_data:
        for item in tables_data:
            print(f"Найдена таблица со страницы: {item['page']}")
            # Для краткости выводим только первые 100 символов JSON
            print(f"JSON (фрагмент): {item['table_json'][:100]}...")

    # print(sys.path)