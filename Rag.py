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
import google.generativeai as genai

# --- Импорт наших файлов ---
from promts import CUSTOM_PROMPT_TEMPLATE
from config import *
from Chanking import *

# --- НАСТРОЙКА ПРОМПТА ---
CUSTOM_PROMPT = PromptTemplate(
    template=CUSTOM_PROMPT_TEMPLATE,
    input_variables=["context", "question"]
)

# 2. Генеративная модель (Gemini API) - УДАЛЕННОЕ ИСПОЛЬЗОВАНИЕ
from langchain_google_genai import ChatGoogleGenerativeAI

# Создаём llm для LangChain — используем уже настроенный ключ
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash-latest",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    credentials=None
)
print("✅ LLM для LangChain настроен.")



# gemini_key = os.getenv("GEMINI_API_KEY")
# genai.configure(api_key=gemini_key)
# llm = genai.GenerativeModel('models/gemini-1.5-flash-latest')
# print("✅ Генеративная модель 'gemini-1.5-flash-latest' настроена.")

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


# --- ФУНКЦИИ RAG-СИСТЕМЫ С QDRANT ---

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
        docs = load_and_split_pdf(r"C:\Users\RGG\Desktop\RagProgramm\docs\123.pdf")
        if not docs:
            return None

        qdrant_db = Qdrant.from_documents(
            docs,
            embeddings,
            path=QDRANT_PATH,
            collection_name=COLLECTION_NAME
        )
        print(f"🎉 Qdrant база знаний создана в {QDRANT_PATH}")

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
        for doc in sources:
            score = doc.metadata.get('_score')
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
        test_question_relevant = " стандарт ОАО «Газпром»; "
        print(f"\n❓ Вопрос (Релевантный): {test_question_relevant}")
        answer_relevant = answer_question(test_question_relevant, qa_chain)
        print("\n------------------------------")
        print("🤖 Ответ:")
        print(answer_relevant)
        print("------------------------------")

        test_question_irrelevant = "Что такое RAG-система?"
        print(f"\n❓ Вопрос (Нерелевантный): {test_question_irrelevant}")
        answer_irrelevant = answer_question(test_question_irrelevant, qa_chain)
        print("\n------------------------------")
        print("🤖 Ответ:")
        print(answer_irrelevant)
        print("------------------------------")