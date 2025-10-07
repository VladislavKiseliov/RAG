import os
import pypdf
import chromadb
from pathlib import Path
from typing import Dict,List,Tuple
import numpy as np
import google.generativeai as genai


# chroma_client = chromadb.PersistentClient(path="./chroma_db")
# collections = chroma_client.create_collection(name="personal_collection")
#
#
# collections.add(
#     documents=[
#         "This is a document about machine learning",
#         "This is another document about data science",
#         "A third document about artificial intelligence"
#     ],
#     metadatas=[
#         {"source": "test1"},
#         {"source": "test2"},
#         {"source": "test3"}
#     ],
#     ids=["id1",
#         "id2",
#         "id3"]
# )
#
# results = collections.query(
#     query_texts=[
#         "This is a query about machine learning and data science"
#     ],
#     n_results=2
# )
#
# print(results)

# Инициализируем API-ключ и модель один раз
API_KEY = "AIzaSyBnZJIbKU_EBreWAtpdFlRbBNlKs-s0bCw"
genai.configure(api_key=API_KEY)
# Модель для генерации ответов. Используется для создания текста.
generative_model = genai.GenerativeModel('models/gemini-1.5-flash-latest')

DIRECTORY_DOCS = r"C:\Users\RGG\Desktop\RagProgramm\docs"
chroma_client = chromadb.PersistentClient(path="./chroma_db")
# collections = chroma_client.create_collection(name="personal_collection")

def list_files(directory: str) -> Dict[str, Path]:
    files = {}
    for filename in os.listdir(directory):
        if os.path.isfile(os.path.join(directory, filename)):
            files[filename] = os.path.join(directory, filename)

    return files

def load_and_split_pdf(file_path)->List[str]:
    text_chunks = []
    try:
        reader = pypdf.PdfReader(file_path)
        for index,page in enumerate(reader.pages):
        # for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                chunks = page_text.split('\n\n')
                text_chunks.extend(chunks)
    except Exception as e:
        print(f"Ошибка при чтении PDF: {e}")
        return []
    return [chunk.strip() for chunk in text_chunks if chunk.strip()]

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

def create_database(chroma_client):
    collections = chroma_client.create_collection(name="personal_collection")
    list_of_files = list_files(DIRECTORY_DOCS)
    print(list_of_files)
    MeteInfo = []
    for filename in list_of_files:
        list_chunks = load_and_split_pdf(list_of_files[filename])
        emdending = create_embeddings(list_chunks)

        list_embeddings = [emd["vector"] for key,emd in emdending.items()]
        list_id_chuks = [str(key) for key in emdending]
        dict_matainfo = {"source": f"{filename}"}
        MetaInfo = [dict_matainfo for key in emdending]
        collections.add(ids =list_id_chuks,  embeddings= list_embeddings,metadatas=MetaInfo)

    return collections

def relevant_text(user_question):
    collections = connect_db(chroma_client)
    vector = create_embeddings(user_question)
    retrieved_context = collections.query(query_embeddings=vector,n_results=3)
    return retrieved_context

def answer(user_question):
    retrieved_context = relevant_text(user_question)
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

def connect_db(chroma_client):
    if not chroma_client.list_collections():
        print(f"{chroma_client.list_collections()=}")
        collections = create_database(chroma_client)
    else:
        print(f"{chroma_client.list_collections()=}")
        collections = chroma_client.list_collections()[0]
    return  collections

if __name__ == "__main__":
    collections= connect_db()

    # Проверим, сколько всего элементов в коллекции
    print("Количество записей в коллекции:", collections.count())

    # Посмотрим первые несколько записей
    peek_data = collections.peek(5)  # первые 5 элементов
    print("\nПервые 5 записей:")
    for i in range(len(peek_data['ids'])):
        print(f"ID: {peek_data['ids'][i]}")
        print(f"Embedding (вектор): {peek_data['embeddings'][i][:5]}...")  # только первые 5 чисел
        print(f"Metadatas: {peek_data['metadatas'][i]}")
        print(f"Documents: {peek_data['documents'][i] if 'documents' in peek_data else 'Нет'}")
        print("-" * 50)