import os
from pathlib import Path
from typing import List

# --- Импорт наших файлов ---
from app.config import *
from .document_processing import *

# --- Загрузка переменных окружения ---
from dotenv import load_dotenv
load_dotenv()  # загружает переменные из .env


from langchain_community.vectorstores import Qdrant
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain_core.prompts import PromptTemplate


def initialization_llm():
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
    return llm

def initialization_embenddings_model():
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

    return embeddings

def initialization_prompt_template():

    # --- НАСТРОЙКА ПРОМПТА ---
    CUSTOM_PROMPT = PromptTemplate(
        template=CUSTOM_PROMPT_TEMPLATE,
        input_variables=["context", "question"]
    )
    return CUSTOM_PROMPT

