# Long-Term Plan And Current Status

Документ фиксирует целевую архитектуру, шаги и текущий прогресс по факту в репозитории.
Проценты — оценка готовности по реализации, а не по качеству.

## 1. Frontend (Слой представления)

Стек: React + Vite + Tailwind CSS + Lucide Icons.

План:
- State Management: Zustand для чатов, токенов и статусов.
- Streaming UI: SSE или WebSockets для посимвольной отдачи.
- Markdown Rendering: Markdown + подсветка кода + кликабельные citations.
- Оптимистичные обновления сообщений.

Текущее состояние:
- Реализовано: базовый React + Vite, авторизация, чат, список чатов, rename/delete, refresh токенов.
- Не реализовано: Zustand, Tailwind, Lucide, стриминг, markdown, citations, оптимистичные статусы сообщений.

Оценка готовности: 35%.

## 2. Backend (Слой API и бизнес-логики)

Стек: FastAPI + SQLAlchemy (PostgreSQL) + Pydantic v2.

План (Domain-Driven Design):
- API Gateway: единая точка входа, JWT, профили, история чатов.
- RAG Engine: изолированный модуль, retrieval + prompt + Gemini.
- Middleware: логирование, обработка ошибок, CORS.
- Взаимодействие:
  - REST для auth и истории.
  - Асинхронное: backend сохраняет файл и кидает задачу в Redis.

Текущее состояние:
- Реализовано: FastAPI API, JWT + refresh, чаты/сообщения, Postgres через SQLAlchemy, базовый RAG.
- Частично: RAG инициализация в API, без отдельного модуля/слоя.
- Не реализовано: DDD-структура, middleware для логирования/ошибок, полноценный gateway, очередь задач для файлов со стороны backend.

Оценка готовности: 45%.

## 3. Ingestion Service (Слой обработки данных)

Стек: FastAPI + Celery + LangChain (или LlamaIndex) + Unstructured.

План:
- Worker: слушает очередь задач.
- Pipeline:
  1) извлечение текста (OCR при необходимости);
  2) семантический чанкинг;
  3) эмбеддинги (bge-m3);
  4) запись в Qdrant с метаданными.

Текущее состояние:
- Реализовано: отдельный FastAPI сервис, Celery worker, Redis broker/back, базовый ingestion PDF.
- Частично: чанкинг по символам, без OCR и семантического чанкинга.
- Не реализовано: Unstructured, продвинутый pipeline, статус прогресса в процентах.

Оценка готовности: 55%.

## 4. Storage Layer (Слой хранения)

План распределения:
- PostgreSQL: пользователи, хэши, метаданные файлов, история чатов, связи документов.
- Qdrant: эмбеддинги + doc_id из Postgres.
- Redis: Celery queue + статус ingestion + кэш ответов LLM.
- S3/MinIO: файлы, изображения, логи.

Текущее состояние:
- Реализовано: Postgres, Qdrant, Redis.
- Частично: метаданные файлов и связи с документами.
- Не реализовано: S3/MinIO, кэш ответов, модель хранения файлов.

Оценка готовности: 40%.

## 5. Схема взаимодействия (Flow)

План:
- Загрузка: User → Frontend → Backend → S3 + Redis (задача).
- Обработка: Worker → берет файл из S3 → чанки → Qdrant → статус в Postgres.
- Вопрос: User → Frontend → Backend → RAG Engine.
- Поиск и ответ: Qdrant → Postgres history → Gemini → streaming в Frontend.

Текущее состояние:
- Реализовано: вопрос → backend → Qdrant → Gemini → ответ.
- Частично: ingestion через отдельный сервис, но без загрузки через backend и без S3.
- Не реализовано: единый flow загрузки, статус прогресса, streaming ответа.

Оценка готовности: 35%.

## 6. Инфраструктура и DevOps

План:
- Docker Compose (dev), Kubernetes (prod), GitHub Actions (CI/CD).
- Internal сети Docker, закрытие БД наружу.
- Observability: LangSmith или LangFuse.

Текущее состояние:
- Реализовано: Docker Compose для базовых сервисов, app и ingestion.
- Не реализовано: K8s, CI/CD, observability, разграничение сетей/доступов.

Оценка готовности: 30%.

## Дорожная карта

Неделя 1:
- Рефакторинг backend.
- Alembic + нормализация моделей Users/Chats/Messages.

Неделя 2:
- Изоляция ingestion service.
- Redis очередь, интеграция с backend.
- Добавление S3/MinIO для файлов.

Неделя 3:
- Апгрейд RAG.
- Гибридный поиск.
- Стриминг ответов на фронтенд.

Неделя 4:
- Агенты.
- Переход на LangGraph для сложной логики.

