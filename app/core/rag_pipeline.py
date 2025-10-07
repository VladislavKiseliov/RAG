import os
from pathlib import Path
from typing import List
import numpy as np
# --- Импорт наших файлов ---
from app.config import *
from .document_processing import *

# --- Загрузка переменных окружения ---
from dotenv import load_dotenv
load_dotenv()  # загружает переменные из .env



from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Qdrant
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import RetrievalQA
from langchain.schema import Document
from langchain.prompts import PromptTemplate
from sentence_transformers import SentenceTransformer
import google.generativeai as genai


# 2. Генеративная модель (Gemini API) - УДАЛЕННОЕ ИСПОЛЬЗОВАНИЕ
# 1. Эта строка должна быть самой первой, чтобы загрузить ключ
# 1. Проверяем ключ (используем правильное имя!)
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_KEY:
    # Используем правильное имя в сообщении об ошибке
    raise EnvironmentError("GEMINI_API_KEY не загружен. Проверьте ваш .env файл и убедитесь, что имя переменной написано правильно.")

# 2. Инициализация LLM: Явно передаем ключ
llm = ChatGoogleGenerativeAI(
    model=LLM_MODEL_NAME,
    google_api_key=GEMINI_KEY # <-- ЯВНО ПЕРЕДАЕМ КЛЮЧ
)
print("✅ LLM для LangChain настроен.")

# 2. Embedding Model
try:
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-m3",
        encode_kwargs={'normalize_embeddings': True}  # <-- ВАЖНО для косинусного поиска!
    )

    print("✅ Локальная модель эмбеддингов настроена.")
except Exception as e:
    print(f"❌ Ошибка настройки HuggingFaceEmbeddings: {e}")
    embeddings = None

# --- НАСТРОЙКА ПРОМПТА ---
CUSTOM_PROMPT = PromptTemplate(
    template=CUSTOM_PROMPT_TEMPLATE,
    input_variables=["context", "question"]
)

def get_retriever():
    """
    Создает или загружает Qdrant базу данных и возвращает LangChain Retriever.
    """
    if embeddings is None:
        print("❌ Эмбеддинги не настроены. Невозможно создать ретривер.")
        return None

    is_indexed = os.path.exists(QDRANT_PATH) and len(list(Path(QDRANT_PATH).glob('*'))) > 0

    if is_indexed:
        print("✅ Qdrant коллекция найдена. Загружаем...")
        qdrant_db = Qdrant.from_existing_collection(
            embedding=embeddings,
            collection_name=COLLECTION_NAME,
            path=QDRANT_PATH
        )
    else:
        print("🆕 Коллекция Qdrant не найдена. Создаем и индексируем документы...")
        list_file = list_pdf_files(DIRECTORY_DOCS)

        # --- ИСПРАВЛЕНИЕ: СБОР ВСЕХ ДОКУМЕНТОВ ---
        all_docs = []
        for file_patch in list_file:
            docs = load_and_split_pdf(file_patch)
            if docs:
                all_docs.extend(docs)  # <--- ДОБАВЛЯЕМ ЧАНКИ В ОБЩИЙ СПИСОК

        if not all_docs:
            print("❌ Документы для индексации не найдены.")
            return None

        # --- ИНДЕКСАЦИЯ ВСЕХ ДОКУМЕНТОВ ОДНИМ ВЫЗОВОМ ---
        qdrant_db = Qdrant.from_documents(
            all_docs,  # <-- Индексируем все чанки
            embeddings,
            path=QDRANT_PATH,
            collection_name=COLLECTION_NAME
        )
        print(f"🎉 Qdrant база знаний, содержащая {len(all_docs)} чанков, создана в {QDRANT_PATH}")

    retriever = qdrant_db.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={
            "k": 5,
            "score_threshold": 0.5
        }
    )
    return retriever


def setup_rag_chain():
    """Настраивает всю цепочку RAG (RetrievalQA)."""
    if llm is None:
        return None

    retriever = get_retriever()
    if retriever is None:
        return None

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": CUSTOM_PROMPT},
        return_source_documents=True
    )
    return qa_chain


def answer_question(question: str, qa_chain: RetrievalQA) -> str:
    """Отвечает на вопрос, используя настроенную цепочку RAG."""


    if not question.strip():
        return "Пожалуйста, задайте корректный вопрос."

    try:

        result = qa_chain.invoke({"query": question})

        answer = result.get('result', "❌ Gemini не смог сгенерировать ответ.")
        sources = result.get('source_documents', [])

        sources_str_list = []
        with open('output1.txt', 'a', encoding='utf-8') as f:
            f.write("\n" + "=" * 50 + "\nНАЧАЛО НОВОГО ОТВЕТА\n" + "=" * 50 + "\n\n")

            # Используем один цикл для итерации по источникам
            for i, doc in enumerate(sources, 1):
                # 1. Записываем метаданные
                # Мы преобразуем словарь в строку, чтобы избежать TypeError
                f.write(f"--- Источник {i} ---\n")
                f.write("Метаданные: " + str(doc.metadata) + "\n")

                # 2. Записываем содержимое страницы (page_content)
                f.write("Текст:\n")
                f.write(doc.page_content)

                f.write("\n" + "-" * 50 + "\n")

        for doc in sources:
            score = doc.metadata.get('_score')
            print(f"{score=}")
            score_display = f"{score:.4f}" if isinstance(score, (float, int)) else 'N/A'

            page_num = doc.metadata.get('page')
            display_page = page_num + 1 if isinstance(page_num, int) else 'N/A'

            sources_str_list.append(
                f"📄 {Path(doc.metadata.get('source', 'Unknown')).name}, стр. {display_page} (Score: {score_display})"
            )

        sources_str = "\n".join(sources_str_list)

        return f"{answer}\n\nИсточники:\n{sources_str}"

    except Exception as e:
        return f"❌ Ошибка при генерации ответа: {e}"


# --- ДЕМОНСТРАЦИЯ И ТЕСТИРОВАНИЕ ---
if __name__ == '__main__':
    qa_chain = setup_rag_chain()

    if qa_chain:
        test_question_relevant = " межкорпоративная стандартизация "
        print(f"\n❓ Вопрос (Релевантный): {test_question_relevant}")
        answer_relevant = answer_question(test_question_relevant, qa_chain)
        print("\n------------------------------")
        print("🤖 Ответ:")
        print(answer_relevant)
        print("------------------------------")

        test_question_irrelevant = "Что такое технические условия"
        print(f"\n❓ Вопрос (Нерелевантный): {test_question_irrelevant}")
        answer_irrelevant = answer_question(test_question_irrelevant, qa_chain)
        print("\n------------------------------")
        print("🤖 Ответ:")
        print(answer_irrelevant)
        print("------------------------------")
