import os
from typing import Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.implementations.SQLITEAlchemy import Data_Base_Alchemy
from app.sevices.security import Auth

# Импорты для RAG и баз данных (закомментированы для отключения функциональности)
# from app.core import answer_question,setup_rag_chain
# from app.db import *
# from app.db.implementations.Qdrant import QdrantManager
# from app.core.initialization import initialization_llm, initialization_embenddings_model, initialization_prompt_template
# from app.config import *



# --- 1. НАСТРОЙКА CORS ---
origins = [
    "http://localhost:5173",  # Ваш React фронтенд
    "http://127.0.0.1:5173",
]
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Импортируем и подключаем маршруты
from app.api.routes import router

app.include_router(router)

# Закомментированные части инициализации (для отключения функциональности RAG)

# Инициализация базы данных при запуске
# @app.on_event("startup")
# async def startup_event():
#
#     pass
#     # # Инициализация компонентов
#     # llm = initialization_llm()
#     # embeddings = initialization_embenddings_model()
#     # prompt_template = initialization_prompt_template()
#     #
#     # # Инициализация Qdrant
#     # qdrant_manager = QdrantManager(
#     #     embeddings=embeddings,
#     #     collection_name=COLLECTION_NAME,
#     #     qdrant_path=QDRANT_PATH,
#     #     docs_directory=DIRECTORY_DOCS
#     # )
#     #
#     # retriever = qdrant_manager.get_retriever()
#     # qa_chain = setup_rag_chain(llm,retriever,prompt_template)