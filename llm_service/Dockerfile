FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=120

COPY llm_service/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-large')"

COPY llm_service/ ./llm_service/

CMD ["uvicorn", "llm_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
