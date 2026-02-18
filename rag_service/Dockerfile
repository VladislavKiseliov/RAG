FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120

WORKDIR /app

COPY rag_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY rag_service/ ./rag_service/

CMD ["uvicorn", "rag_service.main:app", "--host", "0.0.0.0", "--port", "8001"]
