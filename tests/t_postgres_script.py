import os
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from ServiceDataBase.app.implementations.PostgresAlchemy import PostgresAlchemy
from ServiceDataBase.app.models.database_models import Base, Chats, Messages, Users


def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set. Check your .env")

    engine = create_engine(database_url, echo=True)
    SessionLocal = sessionmaker(bind=engine)

    postgres = PostgresAlchemy()

    with SessionLocal() as db:
        # Create a unique user to avoid conflicts.
        username = f"test_user_{uuid.uuid4().hex[:8]}"
        password = "test_password"

        postgres.add_new_user(db, username, password)
        user = postgres.get_user_by_login(db, username)
        if not user:
            raise RuntimeError("User was not created")

        chat_id = uuid.uuid4()
        postgres.add_new_chat(db, chat_id, user.id, "Test chat")

        postgres.add_new_message(db, chat_id, "user", "Hello from test")
        postgres.add_new_message(db, chat_id, "assistant", "Test reply")

        chats = postgres.get_all_chats(db, user.id)
        messages = postgres.get_chat_messages(db, chat_id)

    print("OK")
    print(f"User: {user.id} ({username})")
    print(f"Chats: {len(chats)}")
    print(f"Messages: {len(messages)}")


if __name__ == "__main__":
    main()
