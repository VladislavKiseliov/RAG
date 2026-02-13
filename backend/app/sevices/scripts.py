import json
import os
import uuid

from fastapi import HTTPException
from urllib import request as urllib_request
from urllib import error as urllib_error

from backend.app.api.routes import SessionLocal

INGESTION_SERVICE_URL = os.getenv("INGESTION_SERVICE_URL", "http://localhost:8001")

def _call_rag_service(question: str, urllib_request=None) -> str:
    if not INGESTION_SERVICE_URL:
        raise HTTPException(status_code=500, detail="INGESTION_SERVICE_URL is not set")

    payload = {"question": question}
    url = f"{INGESTION_SERVICE_URL.rstrip('/')}/rag/answer"
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib_request.urlopen(req, timeout=60) as response:
            body = response.read().decode("utf-8")
        response_json = json.loads(body)
        return response_json.get("answer", "")
    except urllib_error.HTTPError as e:
        error_body = e.read().decode("utf-8") if e.fp else ""
        raise HTTPException(
            status_code=e.code,
            detail=error_body or "RAG request failed",
        )
    except urllib_error.URLError as e:
        raise HTTPException(
            status_code=502,
            detail=f"RAG service unreachable: {e.reason}",
        )

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