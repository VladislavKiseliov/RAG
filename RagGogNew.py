# RagGoogle.py

import os
import pypdf
import chromadb
from pathlib import Path
import google.generativeai as genai
from typing import List, Dict

# Настройка Gemini
API_KEY = "AIzaSyBnZJIbKU_EBreWAtpdFlRbBNlKs-s0bCw"
genai.configure(api_key=API_KEY)
embedding_model = 'models/embedding-001'
generative_model = genai.GenerativeModel('models/gemini-1.5-flash-latest')

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
            blocks = [b.strip() for b in text.split('\n\n') if len(b.strip()) > 10]
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
    """Создаёт эмбеддинги для списка текстов. Пропускает None/пустые."""
    print(f"🧠 Создаём эмбеддинги для {len(texts)} текстов...")
    embeddings = []
    for i, text in enumerate(texts):
        if not text or not text.strip():
            print(f"🟡 Пропущен пустой текст (индекс {i})")
            continue
        try:
            response = genai.embed_content(
                model=embedding_model,
                content=text,
                task_type="RETRIEVAL_DOCUMENT"
            )
            embedding = response['embedding']
            embeddings.append(embedding)
        except Exception as e:
            print(f"❌ Ошибка при эмбеддинге текста {i}: {e}")
            continue
    print(f"✅ Готово: {len(embeddings)} эмбеддингов")
    return embeddings


def get_or_create_collection():
    """Получает или создаёт коллекцию с документами."""
    try:
        collection = chroma_client.get_collection(name=COLLECTION_NAME)
        print("✅ Коллекция найдена.")
        return collection
    except Exception:
        print("🆕 Создаём новую коллекцию...")

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

        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=texts  # обязательно!
        )
        print(f"✅ Добавлено {len(embeddings)} чанков из {pdf_file.name}")

    print("🎉 База знаний создана!")
    return collection


def get_relevant_context(query: str, n_results: int = 3) -> List[Dict]:
    """Находит релевантные фрагменты по запросу."""
    collection = get_or_create_collection()

    try:
        query_embedding = genai.embed_content(
            model=embedding_model,
            content=query,
            task_type="RETRIEVAL_QUERY"
        )['embedding']
    except Exception as e:
        print(f"❌ Ошибка при создании эмбеддинга запроса: {e}")
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )

    # Извлекаем данные
    contexts = []
    if not results['documents'] or not results['documents'][0]:
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

    contexts = get_relevant_context(question.strip(), n_results=2)

    if not contexts:
        return "❌ Не удалось найти релевантную информацию по вашему запросу."

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