from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    from app.api.routes import router
    from app.api.admin_routes import router as admin_router
except ModuleNotFoundError as exc:
    if exc.name != "app":
        raise
    from backend.app.api.routes import router
    from backend.app.api.admin_routes import router as admin_router

app.include_router(router)
app.include_router(admin_router)
