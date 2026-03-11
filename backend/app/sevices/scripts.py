import json
import os
import uuid

from fastapi import HTTPException
from urllib import request as urllib_request
from urllib import error as urllib_error
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://myuser:mypassword@localhost:5432/myapp_db")
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine)
RAG_SERVICE_URL = os.getenv("RAG_SERVICE_URL") or os.getenv("INGESTION_SERVICE_URL") or "http://localhost:8001"

def _call_rag_service(question: str) -> dict:
    if not RAG_SERVICE_URL:
        raise HTTPException(status_code=500, detail="RAG_SERVICE_URL is not set")

    payload = {"query": question}
    url = f"{RAG_SERVICE_URL.rstrip('/')}/documents/ask"
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib_request.urlopen(req, timeout=60) as response:
            body = response.read().decode("utf-8")
        response_json = json.loads(body)
        return {
            "answer": response_json.get("answer", ""),
            "sources": response_json.get("sources", []),
        }
    except urllib_error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise HTTPException(status_code=e.code, detail=error_body or "rag_service request failed")
    except urllib_error.URLError as e:
        raise HTTPException(status_code=502, detail=f"rag_service unreachable: {e.reason}")

def parse_uuid(value: str, field_name: str) -> uuid.UUID:
    # Единая проверка UUID и возврат 400 при ошибке.
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")

def get_db():
    # Зависимость FastAPI, возвращающая сессию БД.
    db = SessionLocal()  # Сессия БД.
    try:
        yield db       # Передаем наружу.
    finally:
        db.close()    # Закрываем сессию.
