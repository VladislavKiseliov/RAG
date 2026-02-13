from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- 1. НАСТРОЙКА CORS ---
origins = [
    "http://localhost:5173",  # Ваш React фронтенд
    "http://127.0.0.1:5173",
]
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Импортируем и подключаем маршруты
try:
    from app.api.routes import router
except ModuleNotFoundError as exc:
    if exc.name != "app":
        raise
    from backend.app.api.routes import router

app.include_router(router)

