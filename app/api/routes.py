# --- ЭНДПОИНТЫ ---

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.sevices.security import create_jwt_token

# Создаем роутер для всех эндпоинтов
router = APIRouter()

# --- СХЕМА ДАННЫХ (Pydantic) ---


# Схема для входящих данных авторизации
class LoginRequest(BaseModel):
    username: str
    password: str


class Message(BaseModel):
    user_message: str


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
def login(user_data: LoginRequest) -> Dict[str, Any]:
    """
     Этот маршрут проверяет учетные данные пользователя и возвращает JWT токен, если данные правильные.
    """

    print(f"Пользователь {user_data.username} и пароль {user_data.password}")
    # 💡 ВРЕМЕННАЯ ЗАГЛУШКА: Проверка логина/пароля
    if user_data.username == "test" and user_data.password == "password":
        token = create_jwt_token({"sub": user_data.username})  # "sub" — это subject, в нашем случае имя пользователя
        print(f'{token=}')
        # Успешный ответ, который ждет React:
        return {
            "message": "Login successful",
            "access_token": "fake_jwt_token_for_test",
            "token_type": "bearer",
        }
    else:
        # 🚨 Ошибка: Возвращаем HTTP-код 401 Unauthorized
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль.",
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
# @app.post("/api/conversations")
# def create_conversation():
#     """Создает новый пустой диалог и возвращает его ID, используя константный user_id."""
#     # conversation_id (chat_id) генерируется как уникальная метка времени
#     conversation_id = str(int(time.time() * 1000))
#     conversations[conversation_id] = []
#
#     # Используем константный user_id
#     sqlite.add_new_chat(chat_id=conversation_id, user_id=user_id, title="Новый чат")
#
#     print(f"Создан новый диалог: {conversation_id} для user: {user_id}")
#     return {"conversation_id": conversation_id}
#
#
# @app.get("/api/conversations")
# def get_all_conversations():
#     """Возвращает список всех ID диалогов для константного user_id."""
#     previews = []
#
#     # Используем константный user_id для получения чатов
#     chats = sqlite.get_all_chats(user_id)
#
#     for chat in chats:
#         first_message = chat.get("title", "Новый чат")
#         previews.append({"id": chat["chat_id"], "title": first_message})
#
#     return {"conversations": sorted(previews, key=lambda x: x['id'], reverse=True)}
#
#
# @app.get("/api/conversations/{conversation_id}")
# def get_conversation_history(conversation_id: str):
#     """Возвращает историю сообщений для конкретного диалога (conversation_id)."""
#     # Здесь мы используем conversation_id, переданный в URL, для получения истории
#     # Если вы хотите убедиться, что этот чат принадлежит user_id,
#     # вам нужно изменить sqlite.get_chat_messages так, чтобы он также принимал user_id.
#
#     # ПРОВЕРКА (необязательно, если история всегда берется из БД)
#     if conversation_id not in conversations:
#         # Пытаемся загрузить историю из БД, если ее нет в локальном кеше
#         try:
#             result = sqlite.get_chat_messages(conversation_id)
#             if not result:
#                 raise HTTPException(status_code=404, detail=f"Диалог {conversation_id} не найден")
#             # Если нашли в БД, кешируем локально (для примера)
#             conversations[conversation_id] = result
#         except Exception:
#             raise HTTPException(status_code=404, detail=f"Ошибка БД или диалог {conversation_id} не найден")
#
#     return {"history": conversations[conversation_id]}
#
#
# # --- ОБНОВЛЕННЫЙ ЭНДПОИНТ ДЛЯ ОТПРАВКИ СООБЩЕНИЙ ---
# @app.post("/api/conversations/{conversation_id}/messages")
# def chat_endpoint(conversation_id: str, message: Message):
#     """Обрабатывает сообщение в рамках конкретного диалога (conversation_id)."""
#
#     # Проверка существования диалога
#     if conversation_id not in conversations:
#         # В реальной ситуации здесь нужно проверить БД
#         raise HTTPException(status_code=404, detail="Диалог не найден. Начните новый чат.")
#
#     user_message = message.user_message
#
#     # 1. Сохраняем сообщение пользователя в локальный словарь
#     user_msg_entry = {"role": "user", "content": user_message}
#     conversations[conversation_id].append(user_msg_entry)
#
#     # 2. Сохраняем сообщение пользователя в БД
#     # Используем динамический conversation_id
#     sqlite.add_new_message(conversation_id, "user", user_message)
#
#     # 3. Получаем ответ от RAG-системы
#     # response_text = answer_question(user_message, qa_chain)
#     response_text = 'Test'
#
#     # 4. Сохраняем ответ ассистента в локальный словарь
#     assistant_msg_entry = {"role": "assistant", "content": response_text}
#     conversations[conversation_id].append(assistant_msg_entry)
#
#     # 5. Сохраняем ответ ассистента в БД
#     # Используем динамический conversation_id
#     sqlite.add_new_message(conversation_id, "assistant", response_text)
#
#     return {"response": response_text}
#
#
# # @app.get("/", response_class=HTMLResponse)
# # async def serve_chat_page(request: Request):
# #     """Отдает главную HTML-страницу."""
# #     return templates.TemplateResponse("index.html", {"request": request})
