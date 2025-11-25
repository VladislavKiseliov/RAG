# --- ЭНДПОИНТЫ ---
import os
import uuid
import uuid6
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status,Depends
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker


from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


from app.db.implementations.SQLITEAlchemy import Data_Base_Alchemy
from app.sevices.security import Auth


# Создаем роутер для всех эндпоинтов
router = APIRouter()

DATABASE_URL = os.getenv("SQLITE")
SECRET_KEY = os.getenv("SECRET_KEY")  # В реальной практике генерируйте ключ, например, с помощью 'openssl rand -hex 32', и храните его в безопасности
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))  # Время жизни токена
print(type(ACCESS_TOKEN_EXPIRE_MINUTES))
print(ACCESS_TOKEN_EXPIRE_MINUTES)
engine = create_engine(DATABASE_URL,echo=True)
SessionLocal = sessionmaker(bind=engine)
sqlite = Data_Base_Alchemy()
auth = Auth(SECRET_KEY,ALGORITHM,ACCESS_TOKEN_EXPIRE_MINUTES)

def get_db():
    db = SessionLocal() # Создаем сессию
    try:
        yield db       # Передаем ее эндпоинту
    finally:
        db.close()     # Закрываем сессию (FastAPI это гарантирует)


# --- СХЕМА ДАННЫХ (Pydantic) ---


# Схема для входящих данных авторизации
class LoginRequest(BaseModel):
    username: str
    password: str


class Message(BaseModel):
    user_message: str

class ChatUpdate(BaseModel):
    title: str


# Схема для ответов

# class WalletOperation(BaseModel):
#     operation_type: str = Field(pattern="^(DEPOSIT|WITHDRAW)$")
#     amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
#
# class WalletResponse(BaseModel):
#     uuid: UUID
#     balance: Decimal



# --- ЭНДПОИНТЫ ---


@router.post("/auth/login")
def login(user_data: LoginRequest,db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
     Этот маршрут проверяет учетные данные пользователя и возвращает JWT токен, если данные правильные.
    """

    print(f"Пользователь {user_data.username} и пароль {user_data.password}")
    try:
        # Получить пользователя из бд
        user = sqlite.get_user_by_login(db,user_data.username)
        # Пытаемся получить токен
        if not user:
            hashed_password = auth.get_password_hash(user_data.password)
            sqlite.add_new_user(db,user_data.username,hashed_password)
            user = sqlite.get_user_by_login(db,user_data.username)

        jwt_token = auth.authenticate_user(user.id,user.password,user_data.password)
        print(jwt_token)
        print(f"ID из токена = {auth.get_user_from_token(jwt_token)}")
        return {
                "message": "Login successful",
                "access_token": jwt_token,
                "token_type": "bearer",
            }
    except Exception as e:
        print(f"Login error: {e}")
        # Возвращаем HTTP-код 401 Unauthorized
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

# # Защищённый маршрут, который возвращает информацию о пользователе,
# # если токен в запросе действителен.
# @app.get("/about_me")
# async def about_me(current_user: str = Depends(get_user_from_token)):
#     """
#     Этот маршрут защищен и требует токен. Если токен действителен, мы возвращаем информацию о пользователе.
#     """
#     user = get_user(current_user)
#     if user:
#         return user
#     # Если пользователь не найден, возвращаем ошибку
#     return {"error": "User not found"}


#
#
@router.post("/api/conversations")
def create_conversation(current_user: str = Depends(auth.get_user_from_token),db: Session = Depends(get_db)):
    """Создает новый пустой диалог и возвращает его ID, используя константный user_id."""
    # user_id = current_user

    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    chat_id = uuid6.uuid7()
    result = sqlite.add_new_chat(db,str(chat_id),current_user,'test')
    if not result:
        raise HTTPException(status_code=500, detail="Internal Server Error")

    print(f"Создан новый диалог: {chat_id} для user: {current_user}")
    return {"conversation_id": chat_id}

@router.get("/api/conversations")
def get_all_conversations(current_user: str = Depends(auth.get_user_from_token),db: Session = Depends(get_db)):
    """Возвращает список всех ID диалогов для константного user_id."""
    previews = []

    # Используем константный user_id для получения чатов
    chats = sqlite.get_all_chats(db,current_user)

    for chat in chats:
        first_message = chat.get("title", "Новый чат")
        previews.append({"id": chat["chat_id"], "title": first_message})

    return {"conversations": sorted(previews, key=lambda x: x['id'], reverse=True)}
#
#
@router.get("/api/conversations/{conversation_id}")
def get_conversation_history(conversation_id: str, current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):
    """Возвращает историю сообщений для конкретного диалога (conversation_id)."""
    # Здесь мы используем conversation_id, переданный в URL, для получения истории
    # Если вы хотите убедиться, что этот чат принадлежит user_id,
    # вам нужно изменить sqlite.get_chat_messages так, чтобы он также принимал user_id.

    # Пытаемся загрузить историю из БД, если ее нет в локальном кеше
    try:
        result = sqlite.get_chat_messages(db, conversation_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Диалог {conversation_id} не найден")
        # Если нашли в БД, возвращаем результат
        return {"history": result}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Ошибка БД или диалог {conversation_id} не найден: {str(e)}")
#
#
# --- ОБНОВЛЕННЫЙ ЭНДПОИНТ ДЛЯ ОТПРАВКИ СООБЩЕНИЙ ---
@router.post("/api/conversations/{conversation_id}/messages")
def chat_endpoint(conversation_id: str, message: Message,current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):
    """Обрабатывает сообщение в рамках конкретного диалога (conversation_id)."""

    # # Проверка существования диалога
    # if conversation_id not in conversations:
    #     # В реальной ситуации здесь нужно проверить БД
    #     raise HTTPException(status_code=404, detail="Диалог не найден. Начните новый чат.")

    user_message = message.user_message

    # 1. Сохраняем сообщение пользователя в локальный словарь
    # user_msg_entry = {"role": "user", "content": user_message}
    # conversations[conversation_id].append(user_msg_entry)

    # 2. Сохраняем сообщение пользователя в БД
    # Используем динамический conversation_id
    sqlite.add_new_message(db,conversation_id, "user", user_message)

    # 3. Получаем ответ от RAG-системы
    # response_text = answer_question(user_message, qa_chain)
    response_text = 'Test'

    # 4. Сохраняем ответ ассистента в локальный словарь
    # assistant_msg_entry = {"role": "assistant", "content": response_text}
    # conversations[conversation_id].append(assistant_msg_entry)

    # 5. Сохраняем ответ ассистента в БД
    # Используем динамический conversation_id
    sqlite.add_new_message(db,conversation_id, "assistant", response_text)

    return {"response": response_text}
#
#

# Эндпоинт управлением чатом
@router.patch("/api/chats/{chat_id}/rename")
def update_title_chat(chat_id: str, title_data: ChatUpdate, current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):
    print(f"Updating title for chat_id: {chat_id}")
    print(f"New title: {title_data.title}")
    sqlite.update_chat_title(db, chat_id, title_data.title)
    return {
       "status": "success",
       "message": "Chat title updated successfully"
     }


@router.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str,current_user: str = Depends(auth.get_user_from_token), db: Session = Depends(get_db)):

    sqlite.delete_chat(db,chat_id,current_user)
    return {
       "status": "success",
       "message": "Chat deleted successfully"
     }
