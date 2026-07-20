# --- Модели (Pydantic) ---
import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, field_validator, model_validator, ConfigDict, Field

from backend.models.database_models import ChatType


class DirectChatItem(BaseModel):
    chat_guid: uuid.UUID
    friend_guid: uuid.UUID
    friend_login: str | None = None
    friend_first_name: str | None = None
    friend_last_name: str | None = None
    last_message_content: str | None = None
    updated_at: datetime | None = None

class NewChatCreated(DirectChatItem):
    type: str = "new_chat_created"




class ChatBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    chat_id: int = Field(validation_alias="id")
    chat_guid: uuid.UUID = Field(validation_alias="guid")
    chat_type: Optional[ChatType] = None
    title: Optional[str] = None
    created_by_id: int


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
    is_new: bool = False


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


class CreateDirectChatRequest(BaseModel):
    friend_guid: uuid.UUID


class NoteBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    note_id: int = Field(validation_alias="id")
    note_guid: uuid.UUID = Field(validation_alias="guid")
    title: Optional[str] = None
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)
    links: list[Any] = Field(default_factory=list)
    tags: list[Any] = Field(default_factory=list)
    folder: Optional[str] = None
    reminder: Optional[datetime] = None
    pinned: bool = False
    follow_up: bool = False
    status: str = "draft"
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


class NoteCreateRequest(BaseModel):
    title: Optional[str] = None
    content: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)
    links: list[Any] = Field(default_factory=list)
    tags: list[Any] = Field(default_factory=list)
    folder: Optional[str] = None
    reminder: Optional[datetime] = None
    pinned: bool = False
    follow_up: bool = False


class NoteUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    meta: Optional[dict[str, Any]] = None
    links: Optional[list[Any]] = None
    tags: Optional[list[Any]] = None
    folder: Optional[str] = None
    reminder: Optional[datetime] = None
    pinned: Optional[bool] = None
    follow_up: Optional[bool] = None


class NoteIndexCompleteRequest(BaseModel):
    status: str
    chunk_count: Optional[int] = None
