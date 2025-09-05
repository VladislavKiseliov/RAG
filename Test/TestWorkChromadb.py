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
collections = chroma_client.create_collection(name="personal_collection")

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





list_of_files = list_files(DIRECTORY_DOCS)
print(list_of_files)
for filename in list_of_files:
    list_chunks = load_and_split_pdf(list_of_files[filename])
    emdending = create_embeddings(list_chunks)
    list_embeddings = [emd["vector"] for key,emd in emdending.items()]
    list_id_chuks = [str(key) for key in emdending]
    collections.add(ids =list_id_chuks,  embeddings= list_embeddings)

