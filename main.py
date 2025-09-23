from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict
import time
from Rag import answer_question

app = FastAPI()

templates = Jinja2Templates(directory=".")

# --- НОВОЕ: Вместо простого списка используем словарь для хранения диалогов ---
# В реальном приложении здесь была бы база данных (например, SQLite)
# { "conversation_id_1": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}], ... }
conversations: Dict[str, List[Dict[str, str]]] = {}


class Message(BaseModel):
    user_message: str


# --- НОВЫЕ ЭНДПОИНТЫ ---

@app.post("/api/conversations")
def create_conversation():
    """Создает новый пустой диалог и возвращает его ID."""
    conversation_id = str(int(time.time() * 1000))  # Простой уникальный ID на основе времени
    conversations[conversation_id] = []
    print(f"Создан новый диалог: {conversation_id}")
    return {"conversation_id": conversation_id}


@app.get("/api/conversations")
def get_all_conversations():
    """Возвращает список всех ID диалогов и их первые сообщения для превью."""
    previews = []
    for conv_id, messages in conversations.items():
        first_message = messages[0]['content'] if messages else "Новый чат"
        previews.append({"id": conv_id, "title": first_message})
    return {"conversations": sorted(previews, key=lambda x: x['id'], reverse=True)}  # Новые вверху


@app.get("/api/conversations/{conversation_id}")
def get_conversation_history(conversation_id: str):
    """Возвращает историю сообщений для конкретного диалога."""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Диалог не найден")
    return {"history": conversations[conversation_id]}


# --- ОБНОВЛЕННЫЙ ЭНДПОИНТ ДЛЯ ОТПРАВКИ СООБЩЕНИЙ ---

@app.post("/api/conversations/{conversation_id}/messages")
def chat_endpoint(conversation_id: str, message: Message):
    """Обрабатывает сообщение в рамках конкретного диалога."""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Диалог не найден")

    user_message = message.user_message

    # Сохраняем сообщение пользователя
    conversations[conversation_id].append({"role": "user", "content": user_message})

    # Получаем ответ от RAG-системы
    response_text = answer_question(user_message)

    # Сохраняем ответ ассистента
    conversations[conversation_id].append({"role": "assistant", "content": response_text})

    return {"response": response_text}


@app.get("/", response_class=HTMLResponse)
async def serve_chat_page(request: Request):
    """Отдает главную HTML-страницу."""
    return templates.TemplateResponse("index.html", {"request": request})