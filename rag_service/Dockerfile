# Используем официальный рантайм NVIDIA с CUDA 12.1
FROM nvidia/cuda:12.0.1-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    DEBIAN_FRONTEND=noninteractive

# Устанавливаем репозиторий deadsnakes, Python 3.12, pip и необходимые утилиты
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.12 \
    python3.12-dev \
    curl \
    git \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Скачиваем и ставим актуальный pip для Python 3.12, настраиваем глобальные алиасы
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12 \
    && ln -sf /usr/bin/python3.12 /usr/bin/python \
    && ln -sf /usr/bin/python3.12 /usr/bin/python3

WORKDIR /app

# Сначала копируем только requirements, чтобы эффективно использовать кэш слоев Docker
COPY rag_service/requirements.txt ./requirements.txt

# Обновляем pip и ставим все зависимости (включая GPU-PyTorch через extra-index-url)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Прогреваем модели Docling в образ (layout, tableformer, easyocr) — чтобы первый
# документ в проде не тянул их из сети
RUN docling-tools models download layout tableformer easyocr

# docling-tools download кладёт только english_g2/latin_g2 — для рантайм-конфига
# EasyOcrOptions(lang=["ru", "en"]) нужна ещё cyrillic_g2, докачиваем её в ту же папку
RUN python3.12 -c "import easyocr; easyocr.Reader(['ru', 'en'], model_storage_directory='/root/.cache/docling/models/EasyOcr', download_enabled=True, verbose=False)"

# Копируем исходный код приложения
COPY rag_service/ ./rag_service/

# Дефолтная команда (переопределяется в docker-compose для воркера)
CMD ["uvicorn", "rag_service.main:app", "--host", "0.0.0.0", "--port", "8001"]