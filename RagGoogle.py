import google.generativeai as genai
import os
import pypdf
import numpy as np
import  chromadb

# Инициализируем API-ключ и модель один раз
API_KEY = "AIzaSyBnZJIbKU_EBreWAtpdFlRbBNlKs-s0bCw"
genai.configure(api_key=API_KEY)
# Модель для генерации ответов. Используется для создания текста.
generative_model = genai.GenerativeModel('models/gemini-1.5-flash-latest')


# Работа с векторной базой данных
# Основные переменные
CHROMA_PATH = "docs/test_chroma_db"
EMBED_MODEL = 'models/embedding-001'
COLLECTION_NAME = "Demo_docs"






# Функция для извлечения текста из PDF-файла
def load_and_split_pdf(file_path):
    text_chunks = []
    try:
        reader = pypdf.PdfReader(file_path)
        for index,page in enumerate(reader.pages):
        # for page in reader.pages:
            print(index)
            page_text = page.extract_text()
            print(page_text)
            if page_text:
                chunks = page_text.split('\n\n')
                text_chunks.extend(chunks)
                print(f"{chunks=}")
    except Exception as e:
        print(f"Ошибка при чтении PDF: {e}")
        return []
    return [chunk.strip() for chunk in text_chunks if chunk.strip()]


# Функция для создания эмбеддингов
def create_embeddings(chunks):
    print("Создаю эмбеддинги для PDF-файла. Это может занять некоторое время...")
    embeddings = {}

    for i, chunk in enumerate(chunks):
        if chunk:
            # Правильный вызов: используем genai.embed_content
            embedding = genai.embed_content(
                model='models/embedding-001',
                content=chunk,
                task_type="RETRIEVAL_DOCUMENT"
            )['embedding']
            embeddings[i] = {
                'text': chunk,
                'vector': np.array(embedding)
            }


    print("Эмбеддинги созданы.")
    return embeddings


def find_relevant_text(query, embeddings_db):
    # Правильный вызов: используем genai.embed_content
    query_embedding = genai.embed_content(
        model='models/embedding-001',
        content=query,
        task_type="RETRIEVAL_QUERY"
    )['embedding']

    query_vector = np.array(query_embedding)

    best_match_text = ""
    max_similarity = -1

    for embedding_data in embeddings_db.values():
        # print(f"{embedding_data=}")

        vector = embedding_data['vector']
        # print(f"{vector=}")
        similarity = np.dot(query_vector, vector) / (np.linalg.norm(query_vector) * np.linalg.norm(vector))
        if similarity > max_similarity:
            max_similarity = similarity
            best_match_text = embedding_data['text']

    return best_match_text


def answer(user_question, embeddings_db):
    retrieved_context = \
        (user_question, embeddings_db)
    prompt_template = f"""
    Используй следующий контекст, чтобы ответить на вопрос.
    Если ответ не содержится в контексте, так и скажи, не придумывай информацию.А так же к ответу добавь номер пункта откуда взята информация
    Контекст:
    {retrieved_context}
    Вопрос:
    {user_question}
    """
    try:
        # Используем правильную модель для генерации
        response = generative_model.generate_content(prompt_template)
        if response.text:
            return response.text
        else:
            return "Не удалось получить ответ от модели. Возможно, контекст был недостаточен."
    except Exception as e:
        print(f"Произошла ошибка при генерации контента: {e}")
        return "Произошла ошибка при обработке вашего запроса."



def start(user_question):
    pdf_path = "docs/123.pdf"
    pdf_chunks = load_and_split_pdf(pdf_path)
    embeddings_db = create_embeddings(pdf_chunks)
    if embeddings_db:
        response = answer(user_question, embeddings_db)
        return response
    else:
        return "Не удалось обработать PDF-файл. Проверьте путь и содержимое."




    pdf_path = "docs/123.pdf"
    pdf_chunks = load_and_split_pdf(pdf_path)
    embeddings_db = create_embeddings(pdf_chunks)
    if embeddings_db:
        prompt = "Что такое система норм и нормативов?"
        print(f"Вопрос: {prompt}")
        print("Ответ:")
        print(answer(prompt, embeddings_db))
    else:
        print("Не удалось обработать PDF-файл. Проверьте путь и содержимое.")