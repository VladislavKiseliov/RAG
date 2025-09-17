# RagGoogle_FIXED.py

import os
import pypdf
import chromadb
import numpy as np
from pathlib import Path
import google.generativeai as genai
from typing import List, Dict, Any

from sentence_transformers import SentenceTransformer

# --- КОНФИГУРАЦИЯ ---
# Токен Hugging Face для модели google/embeddinggemma-300m (если она gated)
HF_TOKEN = "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"
# API Key Google для генеративной модели (Gemini)
API_KEY = "AIzaSyBnZJIbKU_EBreWAtpdFlRbBNlKs-s0bCw"

# Инициализация моделей
# 1. Эмбеддинги (SentenceTransformer) - ЛОКАЛЬНОЕ ИСПОЛЬЗОВАНИЕ
try:
    # Загружаем модель ЛОКАЛЬНО с использованием токена HF
    embedding_model = SentenceTransformer("google/embeddinggemma-300m", token=HF_TOKEN)
    print("✅ Локальная модель эмбеддингов 'embeddinggemma-300m' загружена.")
except Exception as e:
    print(f"❌ Ошибка загрузки SentenceTransformer: {e}")
    # Fallback или выход
    embedding_model = None

# 2. Генеративная модель (Gemini API) - УДАЛЕННОЕ ИСПОЛЬЗОВАНИЕ
genai.configure(api_key=API_KEY)
generative_model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
print("✅ Генеративная модель 'gemini-1.5-flash-latest' настроена.")

# Пути
DIRECTORY_DOCS = r"C:\Users\RGG\Desktop\RagProgramm\docs"
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "personal_collection"

# Клиент Chroma
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)


def list_pdf_files(directory: str) -> List[Path]:
    """Возвращает список PDF-файлов."""
    path = Path(directory)
    return [f for f in path.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]


def load_and_split_pdf(file_path: Path) -> List[Dict]:
    """Читает PDF и возвращает список чанков с метаданными."""
    chunks = []
    try:
        reader = pypdf.PdfReader(file_path)
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text or not text.strip():
                print(f"⚠️ Пропущена страница {page_num + 1} (нет текста) в файле {file_path.name}")
                continue

            # Разбиваем на блоки по пустым строкам
            # Убеждаемся, что блоки достаточно длинные
            blocks = [b.strip() for b in text.split('\n\n') if len(b.strip()) > 30]
            for block in blocks:
                chunks.append({
                    "text": block,
                    "source": file_path.name,
                    "page": page_num + 1
                })
    except Exception as e:
        print(f"❌ Ошибка при чтении PDF {file_path.name}: {e}")
    return chunks


def create_embeddings(texts: List[str]) -> List[List[float]]:
    """Создаёт эмбеддинги для списка текстов с использованием SentenceTransformer."""
    if embedding_model is None:
        return []

    print(f"🧠 Создаём эмбеддинги для {len(texts)} текстов (локально)...")

    # 1. Фильтруем пустые тексты
    valid_texts = [text for text in texts if text and text.strip()]

    if not valid_texts:
        print("🟡 Нет корректных текстов для встраивания.")
        return []

    # 2. Используем метод .encode() из SentenceTransformer
    try:
        # SentenceTransformer возвращает numpy array, преобразуем его в List[List[float]]
        embeddings_np = embedding_model.encode(valid_texts, convert_to_numpy=True)
        embeddings = embeddings_np.tolist()

        print(f"✅ Готово: {len(embeddings)} эмбеддингов")
        return embeddings

    except Exception as e:
        print(f"❌ Критическая ошибка при создании эмбеддингов: {e}")
        return []


def get_or_create_collection():
    """Получает или создаёт коллекцию с документами."""
    if embedding_model is None:
        print("❌ Невозможно создать коллекцию: модель эмбеддингов не загружена.")
        return None

    try:
        # Проверяем наличие коллекции. Если есть, возвращаем.
        collection = chroma_client.get_collection(name=COLLECTION_NAME)
        print("✅ Коллекция найдена.")
        return collection
    except Exception:
        # Если нет, создаём
        print("🆕 Создаём новую коллекцию...")

    # Создаём коллекцию без указания embedding_function, т.к. мы передадим эмбеддинги вручную.
    # Для этого Chroma по умолчанию использует E5-small, но мы будем подавлять эту функцию своими
    # эмбеддингами.
    collection = chroma_client.create_collection(name=COLLECTION_NAME)
    pdf_files = list_pdf_files(DIRECTORY_DOCS)

    if not pdf_files:
        print("❌ Нет PDF-файлов в папке:", DIRECTORY_DOCS)
        return collection

    for pdf_file in pdf_files:
        print(f"📄 Обрабатываем: {pdf_file.name}")
        chunks = load_and_split_pdf(pdf_file)
        if not chunks:
            continue

        texts = [c["text"] for c in chunks]
        metadatas = [{"source": c["source"], "page": c["page"]} for c in chunks]
        ids = [f"{pdf_file.stem}_chunk_{i}" for i in range(len(chunks))]

        embeddings = create_embeddings(texts)
        if not embeddings:
            print(f"❌ Не удалось создать эмбеддинги для {pdf_file.name}")
            continue

        # Внимание: здесь мы передаём заранее созданные эмбеддинги!
        collection.add(
            ids=ids[:len(embeddings)],  # Обрезаем id по количеству реальных эмбеддингов
            embeddings=embeddings,
            metadatas=metadatas[:len(embeddings)],
            documents=texts[:len(embeddings)]
        )
        print(f"✅ Добавлено {len(embeddings)} чанков из {pdf_file.name}")

    print("🎉 База знаний создана!")
    return collection


def get_relevant_context(query: str, n_results: int = 3) -> List[Dict]:
    """Находит релевантные фрагменты по запросу."""
    collection = get_or_create_collection()
    if collection is None:
        return []

    if embedding_model is None:
        return []

    try:
        # 1. Создаём эмбеддинг запроса ЛОКАЛЬНО с помощью SentenceTransformer
        # [0] потому что encode возвращает массив массивов (для одного текста - [вектор])
        query_embedding = embedding_model.encode(query, convert_to_numpy=True).tolist()[0]
    except Exception as e:
        print(f"❌ Ошибка при создании эмбеддинга запроса (локально): {e}")
        return []

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
    except Exception as e:
        print(f"❌ Ошибка запроса к Chroma: {e}")
        return []

    # Извлекаем данные
    contexts = []
    if not results.get('documents') or not results['documents'][0]:
        return contexts

    for i in range(len(results['ids'][0])):
        doc = results['documents'][0][i]
        if not doc:
            continue
        contexts.append({
            "text": doc,
            "id": results['ids'][0][i],
            "source": results['metadatas'][0][i].get("source"),
            "page": results['metadatas'][0][i].get("page"),
            "distance": results['distances'][0][i] if 'distances' in results else None
        })
    return contexts


def answer_question(question: str) -> str:
    """
    Отвечает на вопрос, используя RAG.
    Возвращает ответ + источник.
    """
    if not question.strip():
        return "Пожалуйста, задайте корректный вопрос."

    # Находим релевантный контекст
    contexts = get_relevant_context(question.strip(), n_results=2)

    if not contexts:
        return "❌ Не удалось найти релевантную информацию по вашему запросу."

    # ... (Остальная логика остаётся неизменной)

    # Фильтруем пустые тексты
    valid_contexts = [ctx for ctx in contexts if ctx["text"] and ctx["text"].strip()]
    if not valid_contexts:
        return "❌ Найденные фрагменты пусты."

    context_texts = [ctx["text"] for ctx in valid_contexts]
    sources = [
        f"📄 {ctx['source']}, стр. {ctx['page']} (ID: {ctx['id']})"
        for ctx in valid_contexts
    ]

    full_context = "\n\n".join(context_texts)
    sources_str = "\n".join(sources)

    # ... (Остальной промпт остается неизменным)
    prompt = f"""
    Ты — ассистент, отвечающий на вопросы. Твоя задача — извлечь ответ из предоставленного текста.
    Действуй по следующим правилам:
    1.  **Строго придерживайся контекста.** Не используй свои предварительные знания.
    2.  Отвечай на вопрос кратко и по существу, основываясь **исключительно** на приведенном ниже контексте.
    3.  Если в контексте нет информации для ответа на вопрос, напиши только фразу: "В предоставленном контексте ответа нет."
    4.  Цитируй источники в конце ответа.

    **Контекст:**
    ---
    {full_context}
    ---

    **Вопрос:**
    {question}

    **Ответ:**
    [Твой ответ здесь]

    **Источники:**
    {sources_str}
    """

    try:
        response = generative_model.generate_content(prompt)
        if response.text:
            return response.text.strip()
        else:
            return "❌ Gemini не смог сгенерировать ответ."
    except Exception as e:
        return f"❌ Ошибка при генерации ответа: {e}"


# Пример вызова для демонстрации
if __name__ == '__main__':
    # Эта функция запустит создание коллекции, если ее нет.
    # Если она есть, она просто ее получит.
    get_or_create_collection()

    # Пример вопроса
    test_question = "Что такое RAG-система?"
    print(f"\n❓ Вопрос: {test_question}")

    answer = answer_question(test_question)
    print("\n------------------------------")
    print("🤖 Ответ:")
    print(answer)
    print("------------------------------")