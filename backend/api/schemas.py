# --- Модели (Pydantic) ---
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, field_validator, model_validator, ConfigDict, Field


# --- 1. ВХОД В СИСТЕМУ (АУТЕНТИФИКАЦИЯ) ---
class LoginRequest(BaseModel):
    username: str = Field(..., description="Логин или Email пользователя")
    password: str = Field(..., description="Пароль")

# --- 2. РЕГИСТРАЦИЯ (СОЗДАНИЕ) ---
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, description="Уникальный логин")
    password: str = Field(..., description="Пароль")
    password_confirm: str = Field(..., description="Подтверждение пароля")

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Пароль должен содержать минимум 8 символов")
        return v


    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        return self

# --- 3. ВЫДАЧА ДАННЫХ (ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ) ---
class UserProfile(BaseModel):
    """Отдаем пользователю"""

    model_config = ConfigDict(from_attributes=True)
    login: str
    role: str
    first_name: str | None = None
    last_name: str | None = None
    patronymic: str | None = None
    job_title: str | None = None
    department: str | None = None
    email: str | None = None
    created_at: datetime
    updated_at: datetime


# --- 4. ОБНОВЛЕНИЕ ПРОФИЛЯ ---
class UserProfileUpdateRequest(BaseModel):
    """Обновляем"""
    first_name: str | None = None
    last_name: str | None = None
    patronymic: str | None = None
    job_title: str | None = None
    department: str | None = None
    email: str | None = None


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
