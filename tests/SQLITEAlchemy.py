import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker
from sqlalchemy import String, Integer, ForeignKey ,  DateTime , create_engine
from datetime import datetime
from app.db.interfaces.base_db import DataBase


class Base(DeclarativeBase):
    pass

class Chats(Base):

    __tablename__ = "chats"

    chat_id: Mapped[int] = mapped_column(String(100),primary_key=True)
    user_id: Mapped[int] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Messages(Base):

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(String(100),ForeignKey('chats.chat_id'))
    role: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Users(Base):

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(String(100))
    login: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)





# Используем SQLite в файле
# DATABASE_URL = "sqlite:///./test.db"

# engine = create_async_engine(DATABASE_URL, echo=True)
# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(bind=engine)



class Data_Base_Alchemy():

    def __init__(self,DATABASE_URL):
        self.DATABASE_URL = DATABASE_URL
        self.engine = create_engine(self.DATABASE_URL)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def add_new_user(self):
        with self.SessionLocal() as session:
            new_user = Users(chat_id=123, login="john", password="")
            session.add_all([new_user])
            session.commit()

    def get_new_user(self):
        with self.SessionLocal() as session:
            user = session.get(Users, 1)
            print(user.login)

    def add_new_chat(self,chat_id: str, user_id: str, title: str) -> bool:
        """Добавление нового чата в базу данных."""

        with self.SessionLocal() as session:
            chats = Chats(chat_id=chat_id, user_id=user_id, title=title)
            session.add(chats)
            session.commit()


    def create_table(self):
        Base.metadata.create_all(self.engine)








# Асинхронная функция для создания таблиц
# async def create_tables():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)

# Запуск
if __name__ == "__main__":
    Db = Data_Base_Alchemy("sqlite:///../storage/db_chat/alchemy.db")
    Db.add_new_user()
    #create_table()
    #add_new_user()
    # get_new_user()
    # add_new_chat(chat_id='123',user_id="43254",title="test")



