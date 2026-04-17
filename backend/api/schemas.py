# --- Модели (Pydantic) ---
from typing import Optional, Any

from pydantic import BaseModel


# Данные для логина.
class LoginRequest(BaseModel):
    username: str
    password: str


class Message(BaseModel):
    user_message: str

class ChatUpdate(BaseModel):
    title: str


class IngestRequest(BaseModel):
    path: str
    collection: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str
    revoke_all: bool = False


# # Пример дополнительных моделей.

# class WalletOperation(BaseModel):
#     operation_type: str = Field(pattern="^(DEPOSIT|WITHDRAW)$")
#     amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
# Ответ по кошельку (пример).
# class WalletResponse(BaseModel):
#     uuid: UUID
#     balance: Decimal