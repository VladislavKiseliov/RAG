import os
from pathlib import Path
from typing import List, Optional
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


def setup_rag_chain(llm=None, retriever=None, prompt_template=None):
    """Настраивает всю цепочку RAG (RetrievalQA)."""
    # Если параметры не переданы, пытаемся получить их из конфигурации
    if llm is None or retriever is None or prompt_template is None:
        print("⚠️  setup_rag_chain вызван без необходимых параметров")
        return None
        
    if llm is None:
        return None
    if retriever is None:
        return None
        
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": prompt_template},  # Используем prompt_template, а не CUSTOM_PROMPT
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
    # Тестовый блок не будет работать без параметров, поэтому просто выводим сообщение
    print("Для тестирования запустите main.py или используйте API")