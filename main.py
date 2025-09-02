from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from RagGoogle import start

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory=".")

chat_history = []


class Message(BaseModel):
    user_message: str


@app.post("/api/chat")
def chat_endpoint(message: Message):
    """
    Эндпоинт для обработки сообщений чата.
    """
    user_message = message.user_message

    # Здесь мы вызываем твою функцию `answer` и сохраняем настоящий ответ.
    # Я исправил опечатку в имени переменной с 'responce' на 'response'.
    response_text = start(user_message)

    # Добавляем сообщение пользователя и ответ в историю
    chat_history.append({"role": "user", "content": user_message})
    chat_history.append({"role": "assistant", "content": response_text})

    return {"response": response_text}


@app.get("/api/history")
def get_history():
    """
    Эндпоинт для получения всей истории чата.
    """
    return {"history": chat_history}


@app.get("/", response_class=HTMLResponse)
async def serve_chat_page(request: Request):
    """
    Эндпоинт, который отдает HTML-страницу чата.
    """
    return templates.TemplateResponse("index.html", {"request": request})