from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict
import time
from app.core import answer_question,setup_rag_chain
from app.db import *
from app.db.Qdrant import QdrantManager
from app.core.initialization import initialization_llm, initialization_embenddings_model, initialization_prompt_template
from app.config import *




app = FastAPI()
sqlite = DataBaseManager(SQLITE)

# Инициализация компонентов
llm = initialization_llm()
embeddings = initialization_embenddings_model()
prompt_template = initialization_prompt_template()

templates = Jinja2Templates(directory="frontend")

# Инициализация Qdrant
qdrant_manager = QdrantManager(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    qdrant_path=QDRANT_PATH,
    docs_directory=DIRECTORY_DOCS
)

retriever = qdrant_manager.get_retriever()
qa_chain = setup_rag_chain(llm,retriever,prompt_template)



# --- КОНСТАНТНЫЙ ID ПОЛЬЗОВАТЕЛЯ (user_id) ---
# В реальном приложении этот ID извлекается из JWT-токена после входа.
# Сейчас он используется как заглушка.
user_id = 1760010918891
# --- КОНСТАНТНЫЙ ID ПОЛЬЗОВАТЕЛЯ (user_id) ---


# Словарь для хранения диалогов (на случай, если DB не работает или для кеширования)
# Ключ: conversation_id
conversations: Dict[str, List[Dict[str, str]]] = {}


class Message(BaseModel):
    user_message: str


# --- ЭНДПОИНТЫ ---

@app.post("/api/conversations")
def create_conversation():
    """Создает новый пустой диалог и возвращает его ID, используя константный user_id."""
    # conversation_id (chat_id) генерируется как уникальная метка времени
    conversation_id = str(int(time.time() * 1000))
    conversations[conversation_id] = []

    # Используем константный user_id
    sqlite.add_new_chat(chat_id=conversation_id, user_id=user_id, title="Новый чат")

    print(f"Создан новый диалог: {conversation_id} для user: {user_id}")
    return {"conversation_id": conversation_id}


@app.get("/api/conversations")
def get_all_conversations():
    """Возвращает список всех ID диалогов для константного user_id."""
    previews = []

    # Используем константный user_id для получения чатов
    chats = sqlite.get_all_chats(user_id)

    for chat in chats:
        first_message = chat.get("title", "Новый чат")
        previews.append({"id": chat["chat_id"], "title": first_message})

    return {"conversations": sorted(previews, key=lambda x: x['id'], reverse=True)}


@app.get("/api/conversations/{conversation_id}")
def get_conversation_history(conversation_id: str):
    """Возвращает историю сообщений для конкретного диалога (conversation_id)."""
    # Здесь мы используем conversation_id, переданный в URL, для получения истории
    # Если вы хотите убедиться, что этот чат принадлежит user_id,
    # вам нужно изменить sqlite.get_chat_messages так, чтобы он также принимал user_id.

    # ПРОВЕРКА (необязательно, если история всегда берется из БД)
    if conversation_id not in conversations:
        # Пытаемся загрузить историю из БД, если ее нет в локальном кеше
        try:
            result = sqlite.get_chat_messages(conversation_id)
            if not result:
                raise HTTPException(status_code=404, detail=f"Диалог {conversation_id} не найден")
            # Если нашли в БД, кешируем локально (для примера)
            conversations[conversation_id] = result
        except Exception:
            raise HTTPException(status_code=404, detail=f"Ошибка БД или диалог {conversation_id} не найден")

    return {"history": conversations[conversation_id]}


# --- ОБНОВЛЕННЫЙ ЭНДПОИНТ ДЛЯ ОТПРАВКИ СООБЩЕНИЙ ---
@app.post("/api/conversations/{conversation_id}/messages")
def chat_endpoint(conversation_id: str, message: Message):
    """Обрабатывает сообщение в рамках конкретного диалога (conversation_id)."""

    # Проверка существования диалога
    if conversation_id not in conversations:
        # В реальной ситуации здесь нужно проверить БД
        raise HTTPException(status_code=404, detail="Диалог не найден. Начните новый чат.")

    user_message = message.user_message

    # 1. Сохраняем сообщение пользователя в локальный словарь
    user_msg_entry = {"role": "user", "content": user_message}
    conversations[conversation_id].append(user_msg_entry)

    # 2. Сохраняем сообщение пользователя в БД
    # Используем динамический conversation_id
    sqlite.add_new_message(conversation_id, "user", user_message)

    # 3. Получаем ответ от RAG-системы
    response_text = answer_question(user_message, qa_chain)

    # 4. Сохраняем ответ ассистента в локальный словарь
    assistant_msg_entry = {"role": "assistant", "content": response_text}
    conversations[conversation_id].append(assistant_msg_entry)

    # 5. Сохраняем ответ ассистента в БД
    # Используем динамический conversation_id
    sqlite.add_new_message(conversation_id, "assistant", response_text)

    return {"response": response_text}


@app.get("/", response_class=HTMLResponse)
async def serve_chat_page(request: Request):
    """Отдает главную HTML-страницу."""
    return templates.TemplateResponse("index.html", {"request": request})