import uuid
from datetime import datetime

from pydantic import UUID4, BaseModel



# TODO: Add data validation


class ReceiveMessageSchema(BaseModel):
    user_guid: uuid.UUID
    chat_guid: uuid.UUID
    content: str


class SendMessageSchema(BaseModel):
    type: str = "new"
    message_guid: uuid.UUID
    user_guid: uuid.UUID
    chat_guid: uuid.UUID
    content: str
    created_at: datetime
    is_read: bool | None = False
    is_new: bool = False


class MessageReadSchema(BaseModel):
    type: str
    chat_guid: uuid.UUID
    message_guid: uuid.UUID


class UserTypingSchema(BaseModel):
    type: str
    chat_guid: uuid.UUID
    user_guid: uuid.UUID


class AddUserToChatSchema(BaseModel):
    chat_guid: str  # used for websocket communication


class NotifyChatRemovedSchema(BaseModel):
    type: str = "chat_deleted"
    chat_guid: str
