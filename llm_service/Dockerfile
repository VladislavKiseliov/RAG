FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY llm_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY llm_service/ ./llm_service/

CMD ["uvicorn", "llm_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
