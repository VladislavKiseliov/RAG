from langchain_community.document_loaders import PyPDFLoader, PyMuPDFLoader
from langchain_core.documents import Document
from typing import List
from dotenv import load_dotenv

load_dotenv()  # загружает переменные из .env
# --- Импорт наших файлов ---
from app.config import *


def load_and_split_pdf(file_path) -> List[Document]:
    """
    Разбивает PDF-файл и возвращает список объектов LangChain Document.
    """
    # Инициализируем переменную заранее, чтобы избежать ошибок
    split_docs = []

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
        # Возвращаем пустой список в случае ошибки
        return split_docs

    print(f"🎉 Всего чанков готово к индексации: {len(split_docs)}")

    return split_docs


if __name__ == "__main__":
    # list_file = load_and_split_pdf("1234.pdf")
    # loader = PyMuPDFLoader(
    #     "1234.pdf",
    # )
    # docs = loader.load()
    # print(docs[0].page_content)
    from langchain_community.document_loaders import UnstructuredPDFLoader

    # 1. Установите библиотеку: pip install unstructured
    # 2. Инициализируйте загрузчик в режиме "elements"
