"""Временные заглушки API для экранов «База знаний» и «Проекты».

In-memory данные, без обращения к rag_service/БД. Существуют только на время
жизни процесса — перезапуск бэкенда сбрасывает состояние. Заменить на реальную
реализацию, когда появится DDD-слой для этих доменов.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from backend.dependencies import CurrentUserDep

knowledge_router = APIRouter(prefix="/api/knowledge", tags=["knowledge-stub"])
projects_router = APIRouter(prefix="/api/projects", tags=["projects-stub"])


class DocumentStatusUpdate(BaseModel):
    status: str


_COLLECTIONS = [
    {"id": "all", "label": "Вся библиотека", "icon": "▤"},
    {"id": "api", "label": "API и интеграции", "icon": "◇"},
    {"id": "infra", "label": "Инфраструктура", "icon": "◫"},
    {"id": "process", "label": "Процессы", "icon": "❏"},
]

_DOCUMENTS: list[dict] = [
    {
        "id": "api", "title": "API Reference — Orders v2", "type": "OpenAPI 3.1", "type_abbr": "API",
        "collection": "api", "personal": False,
        "size": "1.2 МБ", "pages": 48, "chunk_size": 512, "overlap": 64, "chunks": 312,
        "models": "bge-m3", "dim": 1024, "metric": "cosine",
        "owner": "Платформа", "updated": "2 дня назад", "status": "indexed",
        "summary": "Полное описание REST API сервиса заказов: аутентификация по OAuth2, ресурсы orders и line_items, курсорная пагинация, единый формат ошибок и вебхуки. Версия 2 сохраняет обратную совместимость с v1 через заголовок Accept-Version.",
        "sections": [
            {"title": "Аутентификация", "chunks": 28, "summary": "OAuth2 client_credentials, время жизни access-токена 1 час, скоупы orders:read и orders:write. Ротация секрета без даунтайма."},
            {"title": "Эндпоинты Orders", "chunks": 96, "summary": "CRUD по заказам, фильтры по статусу и периоду, bulk-операции до 500 записей за запрос, идемпотентные ключи для POST."},
            {"title": "Пагинация", "chunks": 34, "summary": "Курсорная модель: параметры limit и cursor, в ответе next_cursor. Offset не поддерживается из-за дрейфа данных."},
            {"title": "Ошибки", "chunks": 52, "summary": "Единый объект error{code, message, details}, маппинг на HTTP-статусы, повторы только для 5xx и 429."},
            {"title": "Вебхуки", "chunks": 41, "summary": "События order.created/updated/cancelled, подпись HMAC-SHA256, ретраи с экспоненциальным backoff до 24 часов."},
        ],
    },
    {
        "id": "cicd", "title": "Руководство по CI/CD", "type": "Markdown", "type_abbr": "MD",
        "collection": "process", "personal": False,
        "size": "340 КБ", "pages": 22, "chunk_size": 512, "overlap": 64, "chunks": 148,
        "models": "bge-m3", "dim": 1024, "metric": "cosine",
        "owner": "DevEx", "updated": "5 дней назад", "status": "indexed",
        "summary": "Стандарт пайплайнов: этапы lint → test → build → deploy, кэширование зависимостей, стратегия деплоя blue-green и процедура отката. Описаны required-чеки и политика веток.",
        "sections": [
            {"title": "Структура пайплайна", "chunks": 44, "summary": "Параллельные джобы lint/test, артефакты между стадиями, матрица версий рантайма."},
            {"title": "Кэширование", "chunks": 30, "summary": "Ключи кэша по lock-файлу, инвалидация при смене базового образа, экономия ~6 мин на сборку."},
            {"title": "Деплой", "chunks": 42, "summary": "Blue-green через два таргет-группы, прогрев и health-checks перед переключением трафика."},
            {"title": "Откат", "chunks": 32, "summary": "Откат одной командой на предыдущий тег, окно автоматического отката по метрикам ошибок."},
        ],
    },
    {
        "id": "arch", "title": "Архитектура сервисов", "type": "Confluence", "type_abbr": "CONF",
        "collection": "infra", "personal": False,
        "size": "2.1 МБ", "pages": 64, "chunk_size": 640, "overlap": 80, "chunks": 268,
        "models": "bge-m3", "dim": 1024, "metric": "cosine",
        "owner": "Архитектура", "updated": "неделю назад", "status": "indexed",
        "summary": "Карта доменных сервисов и их контрактов: orders, billing, notifications, identity. Описаны синхронные вызовы, событийная шина и границы транзакций. Добавлен сервис billing.",
        "sections": [
            {"title": "Доменные границы", "chunks": 58, "summary": "Каждый сервис владеет своими данными, межсервисные обращения только через публичные контракты."},
            {"title": "Событийная шина", "chunks": 72, "summary": "Kafka-топики по доменам, схемы в реестре, at-least-once доставка и дедупликация на стороне потребителя."},
            {"title": "Билинг", "chunks": 66, "summary": "Новый сервис тарификации, идемпотентные начисления, сверка с провайдером платежей раз в сутки."},
            {"title": "Идентичность", "chunks": 72, "summary": "Единый identity-провайдер, JWT с короткими TTL, делегирование скоупов между сервисами."},
        ],
    },
    {
        "id": "runbook", "title": "Runbook: миграция БД на v2", "type": "Markdown", "type_abbr": "MD",
        "collection": "infra", "personal": False,
        "size": "180 КБ", "pages": 14, "chunk_size": 512, "overlap": 64, "chunks": 96,
        "models": "bge-m3", "dim": 1024, "metric": "cosine",
        "owner": "SRE", "updated": "3 дня назад", "status": "indexed",
        "summary": "Пошаговый сценарий перехода схемы на v2: dry-run, посервисное применение миграций, проверка консистентности и план отката. Указаны окна обслуживания и владельцы шагов.",
        "sections": [
            {"title": "Подготовка", "chunks": 22, "summary": "Снапшот БД, проверка свободного места, заморозка схемных изменений на время окна."},
            {"title": "Dry-run", "chunks": 26, "summary": "Прогон миграций на реплике, замер длительности блокировок, отчёт о расхождениях."},
            {"title": "Применение", "chunks": 30, "summary": "Посервисный rollout, online-DDL для больших таблиц, контроль лага репликации."},
            {"title": "Откат", "chunks": 18, "summary": "Обратные миграции и восстановление из снапшота, критерии принятия решения об откате."},
        ],
    },
    {
        "id": "style", "title": "Гайд по код-стайлу", "type": "Markdown", "type_abbr": "MD",
        "collection": "process", "personal": False,
        "size": "96 КБ", "pages": 11, "chunk_size": 384, "overlap": 48, "chunks": 64,
        "models": "bge-m3", "dim": 1024, "metric": "cosine",
        "owner": "DevEx", "updated": "2 недели назад", "status": "indexed",
        "summary": "Соглашения по именованию, форматированию и структуре модулей, правила ревью и требования к покрытию тестами. Линтер и форматтер настроены как pre-commit и required-чек в CI.",
        "sections": [
            {"title": "Именование", "chunks": 18, "summary": "Единые правила для пакетов, типов и функций, запрет на сокращения вне согласованного списка."},
            {"title": "Ревью", "chunks": 24, "summary": "Минимум один аппрув, чеклист ревьюера, ограничение размера PR для скорости проверки."},
            {"title": "Тесты", "chunks": 22, "summary": "Порог покрытия 80%, обязательные тесты на баг-фиксы, изоляция внешних зависимостей."},
        ],
    },
    {
        "id": "onb", "title": "Onboarding инженера", "type": "Confluence", "type_abbr": "CONF",
        "collection": "process", "personal": False,
        "size": "420 КБ", "pages": 18, "chunk_size": 512, "overlap": 64, "chunks": 112,
        "models": "bge-m3", "dim": 1024, "metric": "cosine",
        "owner": "People", "updated": "месяц назад", "status": "indexed",
        "summary": "План первых двух недель: доступы, локальное окружение, первый коммит и знакомство с командами. Чеклист по дням и ответственные наставники для каждого блока.",
        "sections": [
            {"title": "Доступы", "chunks": 26, "summary": "Запрос прав через единый портал, минимально необходимый набор на старте, ревизия через месяц."},
            {"title": "Окружение", "chunks": 48, "summary": "Скрипт быстрой настройки, контейнеры для зависимостей, типовые проблемы и их решения."},
            {"title": "Первый коммит", "chunks": 38, "summary": "Подобранная good-first-issue, парное ревью, прохождение всего пайплайна до прода."},
        ],
    },
    {
        "id": "p1", "title": "Заметки: архитектура биллинга", "type": "Markdown", "type_abbr": "MD",
        "collection": "personal", "personal": True,
        "size": "64 КБ", "pages": 6, "chunk_size": 384, "overlap": 48, "chunks": 36,
        "models": "bge-m3", "dim": 1024, "metric": "cosine",
        "owner": "Влад Логинов", "updated": "сегодня", "status": "indexed",
        "summary": "Личные заметки по новому сервису биллинга: модель тарифов, идемпотентность начислений, открытые вопросы по сверке с провайдером. Черновик для обсуждения на следующем синке.",
        "sections": [
            {"title": "Модель тарифов", "chunks": 14, "summary": "Тарифные планы как версионируемые сущности, расчёт по событиям использования."},
            {"title": "Идемпотентность", "chunks": 12, "summary": "Ключ операции = (договор, период, тип), защита от двойного начисления при ретраях."},
            {"title": "Открытые вопросы", "chunks": 10, "summary": "Окно сверки с провайдером и обработка частичных возвратов — нужно решение архитектора."},
        ],
    },
    {
        "id": "p2", "title": "Чеклист релиза", "type": "PDF", "type_abbr": "PDF",
        "collection": "personal", "personal": True,
        "size": "48 КБ", "pages": 3, "chunk_size": 384, "overlap": 48, "chunks": 22,
        "models": "bge-m3", "dim": 1024, "metric": "cosine",
        "owner": "Влад Логинов", "updated": "вчера", "status": "indexed",
        "summary": "Персональный чеклист перед выкаткой: фиче-флаги, миграции, метрики и дежурный. Использую как финальную проверку перед нажатием deploy.",
        "sections": [
            {"title": "Перед деплоем", "chunks": 12, "summary": "Состояние фиче-флагов, обратимость миграций, готовность дашбордов."},
            {"title": "После деплоя", "chunks": 10, "summary": "Контроль ошибок и латентности первые 30 минут, план отката под рукой."},
        ],
    },
]

_PROJECTS: list[dict] = [
    {
        "id": "pay", "name": "Платёжный шлюз v2", "glyph": "ПШ", "status": "В работе", "kind": "active",
        "lead": "Ведёт Влад", "deadline": "до 12 июля",
        "desc": "Новая версия платёжного шлюза: переход на идемпотентные операции, поддержка нескольких провайдеров и сверка транзакций.",
        "members": [
            {"init": "ВЛ", "name": "Влад Логинов", "role": "Тимлид"},
            {"init": "ИП", "name": "Иван Петров", "role": "Бэкенд"},
            {"init": "СК", "name": "Соня Кравец", "role": "QA"},
        ],
        "updated": "2 ч назад",
        "tasks": [
            {"t": "Контракт API провайдера", "done": True, "assignee": "ИП"},
            {"t": "Идемпотентность начислений", "done": True, "assignee": "ИП"},
            {"t": "Сверка транзакций (cron)", "done": True, "assignee": "ВЛ"},
            {"t": "Обработка частичных возвратов", "done": False, "assignee": "ВЛ"},
            {"t": "Нагрузочное тестирование", "done": False, "assignee": "СК"},
            {"t": "Документация для интеграторов", "done": False, "assignee": "ВЛ"},
        ],
        "files": [
            {"name": "Спецификация шлюза.pdf", "ext": "PDF", "size": "1.4 МБ", "by": "Влад", "when": "2 ч назад"},
            {"name": "provider-contract.yaml", "ext": "YAML", "size": "24 КБ", "by": "Иван", "when": "вчера"},
            {"name": "Схема сверки.fig", "ext": "FIG", "size": "3.1 МБ", "by": "Соня", "when": "2 дня"},
            {"name": "reconcile.sql", "ext": "SQL", "size": "8 КБ", "by": "Влад", "when": "3 дня"},
            {"name": "Тест-план.docx", "ext": "DOC", "size": "120 КБ", "by": "Соня", "when": "4 дня"},
        ],
        "docs": [
            {"title": "API Reference — Orders v2", "points": 312},
            {"title": "Архитектура сервисов", "points": 268},
        ],
        "activity": [
            {"who": "ИП", "text": "Иван закрыл задачу «Идемпотентность начислений»", "when": "2 часа назад"},
            {"who": "ВЛ", "text": "Влад добавил файл «Спецификация шлюза.pdf»", "when": "2 часа назад"},
            {"who": "СК", "text": "Соня оставила комментарий к тест-плану", "when": "вчера"},
            {"who": "ИП", "text": "Иван открыл ветку feature/multi-provider", "when": "2 дня назад"},
        ],
    },
    {
        "id": "mig", "name": "Миграция БД на v2", "glyph": "МБ", "status": "На ревью", "kind": "review",
        "lead": "Ведёт SRE", "deadline": "до 30 июня",
        "desc": "Перевод схемы базы данных на версию 2 с минимальным даунтаймом: dry-run, посервисный rollout и план отката.",
        "members": [
            {"init": "АР", "name": "Артём Рыжов", "role": "SRE"},
            {"init": "ВЛ", "name": "Влад Логинов", "role": "Ревью"},
        ],
        "updated": "5 ч назад",
        "tasks": [
            {"t": "Снапшот и заморозка схемы", "done": True, "assignee": "АР"},
            {"t": "Dry-run на реплике", "done": True, "assignee": "АР"},
            {"t": "Online-DDL для больших таблиц", "done": True, "assignee": "АР"},
            {"t": "Финальное ревью", "done": False, "assignee": "ВЛ"},
        ],
        "files": [
            {"name": "Runbook миграции.md", "ext": "MD", "size": "180 КБ", "by": "Артём", "when": "5 ч назад"},
            {"name": "migration_v2.sql", "ext": "SQL", "size": "42 КБ", "by": "Артём", "when": "вчера"},
            {"name": "rollback.sql", "ext": "SQL", "size": "18 КБ", "by": "Артём", "when": "вчера"},
        ],
        "docs": [{"title": "Runbook: миграция БД на v2", "points": 96}],
        "activity": [
            {"who": "АР", "text": "Артём отправил проект на ревью", "when": "5 часов назад"},
            {"who": "АР", "text": "Артём приложил rollback.sql", "when": "вчера"},
        ],
    },
    {
        "id": "red", "name": "Редизайн портала", "glyph": "РП", "status": "В работе", "kind": "active",
        "lead": "Ведёт дизайн", "deadline": "до 20 июля",
        "desc": "Обновление инженерного портала: новая структура навигации, тёмная и светлая темы, единая система компонентов.",
        "members": [
            {"init": "СК", "name": "Соня Кравец", "role": "Дизайн"},
            {"init": "ВЛ", "name": "Влад Логинов", "role": "Фронтенд"},
        ],
        "updated": "вчера",
        "tasks": [
            {"t": "Аудит текущих экранов", "done": True, "assignee": "СК"},
            {"t": "Система токенов и тем", "done": True, "assignee": "СК"},
            {"t": "Сборка библиотеки компонентов", "done": False, "assignee": "ВЛ"},
            {"t": "Перенос экранов", "done": False, "assignee": "ВЛ"},
            {"t": "Юзабилити-тест", "done": False, "assignee": "СК"},
        ],
        "files": [
            {"name": "Портал — макеты.fig", "ext": "FIG", "size": "8.2 МБ", "by": "Соня", "when": "вчера"},
            {"name": "Гайд по темам.pdf", "ext": "PDF", "size": "640 КБ", "by": "Соня", "when": "2 дня"},
        ],
        "docs": [{"title": "Гайд по код-стайлу", "points": 64}],
        "activity": [
            {"who": "СК", "text": "Соня обновила макеты в Figma", "when": "вчера"},
            {"who": "ВЛ", "text": "Влад начал сборку компонентов", "when": "2 дня назад"},
        ],
    },
    {
        "id": "ci", "name": "Ускорение CI/CD", "glyph": "CI", "status": "Планирование", "kind": "plan",
        "lead": "Ведёт DevEx", "deadline": "до 5 авг",
        "desc": "Сокращение времени сборки и деплоя: кэширование зависимостей, параллельные джобы и blue-green выкатка.",
        "members": [{"init": "ИП", "name": "Иван Петров", "role": "DevEx"}],
        "updated": "3 дня назад",
        "tasks": [
            {"t": "Замер текущих времён", "done": True, "assignee": "ИП"},
            {"t": "План кэширования", "done": False, "assignee": "ИП"},
            {"t": "Параллелизация тестов", "done": False, "assignee": "ИП"},
        ],
        "files": [{"name": "Метрики сборок.xlsx", "ext": "XLS", "size": "56 КБ", "by": "Иван", "when": "3 дня"}],
        "docs": [{"title": "Руководство по CI/CD", "points": 148}],
        "activity": [{"who": "ИП", "text": "Иван собрал метрики текущих сборок", "when": "3 дня назад"}],
    },
    {
        "id": "bil", "name": "Биллинг", "glyph": "БИ", "status": "В работе", "kind": "active",
        "lead": "Ведёт Влад", "deadline": "до 28 июля",
        "desc": "Запуск сервиса тарификации: модель тарифов, начисления по событиям использования и сверка с провайдером платежей.",
        "members": [
            {"init": "ВЛ", "name": "Влад Логинов", "role": "Тимлид"},
            {"init": "АР", "name": "Артём Рыжов", "role": "Бэкенд"},
        ],
        "updated": "сегодня",
        "tasks": [
            {"t": "Модель тарифных планов", "done": True, "assignee": "ВЛ"},
            {"t": "Начисления по событиям", "done": False, "assignee": "АР"},
            {"t": "Сверка с провайдером", "done": False, "assignee": "АР"},
            {"t": "Отчёты по начислениям", "done": False, "assignee": "ВЛ"},
        ],
        "files": [
            {"name": "Заметки: биллинг.md", "ext": "MD", "size": "64 КБ", "by": "Влад", "when": "сегодня"},
            {"name": "billing-schema.json", "ext": "JSON", "size": "12 КБ", "by": "Артём", "when": "вчера"},
        ],
        "docs": [{"title": "Архитектура сервисов", "points": 268}],
        "activity": [{"who": "ВЛ", "text": "Влад зафиксировал модель тарифов", "when": "сегодня"}],
    },
]


@knowledge_router.get("/documents")
async def list_documents(current_user: CurrentUserDep):
    return {"documents": _DOCUMENTS, "collections": _COLLECTIONS}


@knowledge_router.post("/documents")
async def upload_document(current_user: CurrentUserDep, file: UploadFile = File(...)):
    content = await file.read()
    kb = max(8, round(len(content) / 1024))
    chunks = max(6, round(kb / 1.6))
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "txt").upper()
    abbr_map = {"PDF": "PDF", "DOCX": "DOC", "DOC": "DOC", "MD": "MD", "MARKDOWN": "MD", "TXT": "TXT"}
    title = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
    doc = {
        "id": f"up{uuid.uuid4().hex[:8]}", "title": title, "type": ext, "type_abbr": abbr_map.get(ext, ext[:4]),
        "collection": "personal", "personal": True,
        "size": f"{kb / 1024:.1f} МБ" if kb >= 1024 else f"{kb} КБ",
        "pages": max(1, round(chunks / 8)), "chunk_size": 384, "overlap": 48, "chunks": chunks,
        "models": "bge-m3", "dim": 1024, "metric": "cosine",
        "owner": current_user.login or "Пользователь", "updated": "только что", "status": "processing",
        "summary": "Документ загружен и разбивается на чанки. Краткое содержание появится после индексации и записи векторов в базу.",
        "sections": [{"title": "Документ", "chunks": chunks, "summary": "Идёт извлечение текста, чанкинг и расчёт эмбеддингов."}],
    }
    _DOCUMENTS.insert(0, doc)
    return doc


@knowledge_router.patch("/documents/{doc_id}")
async def update_document_status(doc_id: str, payload: DocumentStatusUpdate, current_user: CurrentUserDep):
    for doc in _DOCUMENTS:
        if doc["id"] == doc_id:
            doc["status"] = payload.status
            if payload.status == "indexed":
                doc["summary"] = "Документ проиндексирован: текст разбит на чанки, эмбеддинги записаны в векторную базу. Можно искать и спрашивать ассистента."
                doc["updated"] = "только что"
            return doc
    return {"error": "not_found"}


@projects_router.get("")
async def list_projects(current_user: CurrentUserDep):
    return {"projects": _PROJECTS}
