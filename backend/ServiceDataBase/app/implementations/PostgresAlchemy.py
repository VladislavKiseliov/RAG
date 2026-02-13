from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session

from ServiceDataBase.app.interfaces.base_db import DataBase
from ServiceDataBase.app.models.database_models import Chats, Messages, Users, RefreshTokens


class PostgresAlchemy(DataBase):
    """PostgreSQL implementation of the database interface using SQLAlchemy ORM."""

    def add_new_chat(self, db: Session, chat_id: uuid.UUID, user_id: uuid.UUID, title: str) -> bool:
        """Add a new chat to the database."""
        try:
            chats = Chats(chat_id=chat_id, user_id=user_id, title=title)
            db.add(chats)
            db.commit()
            return True

        except IntegrityError:
            db.rollback()
            raise Exception("Chat already exists")
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when adding chat: {str(e)}")

    def get_all_chats(self, db: Session, user_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Get list of all chats for a user."""
        try:
            stmt = select(Chats).filter_by(user_id=user_id)
            chats = db.scalars(stmt).all()

            result = []
            for chat in chats:
                result.append(
                    {
                        "chat_id": chat.chat_id,
                        "title": chat.title,
                        "created_at": chat.created_at,
                        "updated_at": chat.updated_at,
                    }
                )
            return result
        except SQLAlchemyError as e:
            raise Exception(f"Database error when getting chats: {str(e)}")

    def update_chat_title(self, db: Session, chat_id: uuid.UUID, user_id: uuid.UUID, new_title: str) -> bool:
        """Update a chat title."""
        try:
            chat = (
                db.query(Chats)
                .filter(Chats.chat_id == chat_id, Chats.user_id == user_id)
                .first()
            )

            if not chat:
                return False

            chat.title = new_title
            chat.updated_at = datetime.utcnow()
            db.commit()

            return True

        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when updating chat title: {str(e)}")

    def delete_chat(self, db: Session, chat_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete a chat and its related messages."""
        try:
            chat = (
                db.query(Chats)
                .filter(Chats.chat_id == chat_id, Chats.user_id == user_id)
                .first()
            )

            if not chat:
                return False

            db.delete(chat)
            db.commit()

            return True

        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when deleting chat: {str(e)}")

    def add_new_message(self, db: Session, chat_id: uuid.UUID, role: str, content: str) -> bool:
        """Add a new message to a chat."""
        try:
            message = Messages(chat_id=chat_id, role=role, content=content)
            db.add(message)
            db.commit()
            return True
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when adding message: {str(e)}")

    def get_chat_messages(
            self, db: Session, chat_id: uuid.UUID,user_id:uuid.UUID, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get chat message history."""
        try:
            stmt = (
                select(Messages)
                .join(Chats, Messages.chat_id == Chats.chat_id)
                .filter(Messages.chat_id == chat_id, Chats.user_id == user_id)
                .order_by(Messages.created_at)
                .limit(limit or None)
            )

            messages = db.scalars(stmt).all()

            result = []
            for message in messages:
                result.append(
                    {
                        "id": message.id,
                        "role": message.role,
                        "content": message.content,
                        "created_at": message.created_at,
                    }
                )
            return result
        except SQLAlchemyError as e:
            raise Exception(f"Database error when getting messages: {str(e)}")

    def delete_message(self, db: Session, message_id: int, chat_id: uuid.UUID) -> bool:
        """Delete a specific message by id and chat id."""
        try:
            message = (
                db.query(Messages)
                .filter(Messages.id == message_id, Messages.chat_id == chat_id)
                .first()
            )

            if not message:
                return False

            db.delete(message)
            db.commit()

            return True
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when deleting message: {str(e)}")

    def add_new_user(self, db: Session, login: str, password: str):
        """Add a new user to the database."""
        try:
            new_user = Users(login=login, password=password)
            db.add(new_user)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise Exception("User with this login already exists")
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when adding user: {str(e)}")

    def get_user(self, db: Session, user_id: uuid.UUID) -> Optional[Users]:
        """Get a user by id."""
        try:
            user = db.get(Users, user_id)
            return user
        except SQLAlchemyError as e:
            raise Exception(f"Database error when getting user: {str(e)}")

    def get_user_by_login(self, db: Session, user_name: str):
        """Get a user by login."""
        try:
            stmt = select(Users).where(Users.login == user_name)
            user = db.scalars(stmt).first()
            return user
        except SQLAlchemyError as e:
            raise Exception(f"Database error when getting user by login: {str(e)}")

    def add_refresh_token(self, db: Session, user_id: uuid.UUID, token: str, expires_at: datetime) -> None:
        """Store a refresh token for a user."""
        try:
            refresh = RefreshTokens(user_id=user_id, token=token, expires_at=expires_at, revoked=False)
            db.add(refresh)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise Exception("Refresh token already exists")
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when adding refresh token: {str(e)}")

    def get_refresh_token(self, db: Session, token: str) -> Optional[RefreshTokens]:
        """Fetch refresh token entry."""
        try:
            stmt = select(RefreshTokens).where(RefreshTokens.token == token)
            return db.scalars(stmt).first()
        except SQLAlchemyError as e:
            raise Exception(f"Database error when getting refresh token: {str(e)}")

    def revoke_refresh_token(self, db: Session, token: str) -> bool:
        """Revoke a refresh token."""
        try:
            refresh = db.query(RefreshTokens).filter(RefreshTokens.token == token).first()
            if not refresh:
                return False
            refresh.revoked = True
            db.commit()
            return True
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when revoking refresh token: {str(e)}")

    def revoke_all_refresh_tokens(self, db: Session, user_id: uuid.UUID) -> int:
        """Revoke all refresh tokens for a user."""
        try:
            count = (
                db.query(RefreshTokens)
                .filter(RefreshTokens.user_id == user_id, RefreshTokens.revoked.is_(False))
                .update({"revoked": True})
            )
            db.commit()
            return count
        except SQLAlchemyError as e:
            db.rollback()
            raise Exception(f"Database error when revoking user tokens: {str(e)}")
