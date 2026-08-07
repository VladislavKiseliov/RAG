"""API для экрана «База знаний» (чтение) и заглушка «Проекты».

Чтение документов (`GET /api/knowledge/documents`) проксирует и агрегирует
реальные данные из rag_service (главы, таблицы, статус индексации). Загрузка
(`POST`/`PATCH`) — временная заглушка на in-memory данных: реальный upload
через основной фронт идёт через presigned-URL-пайплайн (как в admin-panel) и
пока не подключён, поэтому «загруженный» документ не появится в списке после
следующего обновления страницы.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.dependencies import CurrentUserDep
from backend.utils.http_clients import rag_client

knowledge_router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
projects_router = APIRouter(prefix="/api/projects", tags=["projects-stub"])

_TYPE_ABBR_BY_EXT = {
    "pdf": "PDF", "docx": "DOC", "doc": "DOC",
    "md": "MD", "markdown": "MD", "txt": "TXT",
}
_STATUS_TO_UI = {"completed": "indexed"}


class DocumentStatusUpdate(BaseModel):
    status: str


_COLLECTIONS = [
    {"id": "all", "label": "Вся библиотека", "icon": "▤"},
]

_DOCUMENTS: list[dict] = []


def _format_size(file_size: int | None) -> str:
    if not file_size:
        return "—"
    kb = file_size / 1024
    return f"{kb / 1024:.1f} МБ" if kb >= 1024 else f"{round(kb)} КБ"


def _split_ext(filename: str) -> tuple[str, str]:
    if "." not in filename:
        return filename, "txt"
    title, ext = filename.rsplit(".", 1)
    return title, ext.lower()


def _to_ui_document(summary: dict, detail: dict | None) -> dict:
    """Map rag_service document (summary + optional detail) to the KB screen shape.

    Полей `collection`/`personal`/`owner`/`chunk_size`/`overlap`/`models`/`dim`/
    `metric` в rag_service нет (нет тегов документа, нет привязки к пользователю,
    чанкинг не токен-оконный). Оставлены как явные заглушки по договорённости —
    не выдумываем правдоподобные числа. `pages`/`chapters_count`/`tables_count`
    рag_service считает и отдаёт (page_count/chapter_count/table_count в
    DocumentDetailResponse) — только в `detail`, не в `summary` (списочный
    ответ их не содержит).
    """
    title, ext = _split_ext(summary["filename"])
    detail = detail or {}
    chapters = detail.get("chapters", [])

    return {
        "id": summary["doc_id"],
        "title": title,
        "type": ext.upper(),
        "type_abbr": _TYPE_ABBR_BY_EXT.get(ext, ext.upper()[:4]),
        "collection": "all",
        "personal": False,
        "size": _format_size(summary.get("size")),
        "pages": detail.get("page_count"),
        "chunk_size": None,
        "overlap": None,
        "chunks": summary.get("chunk_count"),
        "chapters_count": detail.get("chapter_count"),
        "tables_count": detail.get("table_count"),
        "models": None,
        "dim": None,
        "metric": None,
        "owner": "—",
        "updated": summary["created_at"][:10],
        "status": _STATUS_TO_UI.get(summary["status"], "processing"),
        "file_url": detail.get("file_url"),
        "summary": detail.get("summary") or "Автоматическое резюме документа пока не сформировано.",
        "sections": [
            {
                "title": chapter["title"],
                "chunks": None,
                "summary": chapter.get("summary") or "Саммари главы пока не сформировано.",
            }
            for chapter in chapters
        ],
    }


async def _fetch_documents_from_rag_service() -> list[dict]:
    """Только список — без деталей (глав) на каждый документ.

    Список нужен карточкам (title/summary/chunks/size/status — ни одно поле не требует
    chapters), поэтому раньше N+1-запрос на детали каждого документа был просто не нужен:
    главы (`sections`) грузятся лениво через GET /documents/{doc_id} только когда юзер
    реально открывает документ (см. `get_document_detail` ниже, `useKnowledgeBase.js::openDoc`).
    """
    list_response = await rag_client.get("/documents")
    list_response.raise_for_status()
    summaries = list_response.json()

    return [_to_ui_document(summary, None) for summary in summaries]

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
    documents = await _fetch_documents_from_rag_service()
    return {"documents": documents, "collections": _COLLECTIONS}


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


@knowledge_router.get("/documents/{doc_id}")
async def get_document_detail(doc_id: str, current_user: CurrentUserDep):
    """Детали одного документа (главы для оглавления читалки) — грузится лениво при открытии,
    не всей библиотекой сразу (см. _fetch_documents_from_rag_service)."""
    response = await rag_client.get(f"/documents/{doc_id}")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Document not found")
    response.raise_for_status()
    detail = response.json()
    return _to_ui_document(detail, detail)


@knowledge_router.get("/documents/{doc_id}/chapters/{chapter_idx}")
async def get_document_chapter(doc_id: str, chapter_idx: int, current_user: CurrentUserDep):
    """Полный текст главы и её таблицы — проксирует rag_service."""
    response = await rag_client.get(f"/documents/{doc_id}/chapters/{chapter_idx}")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="Chapter not found")
    response.raise_for_status()
    return response.json()


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
