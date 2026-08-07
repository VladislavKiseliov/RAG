"""API для экрана «База знаний».

Чтение (`list_documents`/`get_document_detail`/`get_document_chapter`) проксирует и
агрегирует реальные данные из rag_service (главы, таблицы, статус индексации).

`upload_document`/`update_document_status` — ЗАГЛУШКА на in-memory `_DOCUMENTS`: реальный
upload через основной фронт идёт через presigned-URL-пайплайн (как в admin-panel) и пока
не подключён сюда. `_DOCUMENTS` при этом никогда не читается `list_documents` (тот всегда
берёт список свежим из rag_service) — то есть загруженный через этот эндпоинт документ
не появится в списке после следующего обновления страницы, даже в рамках одной сессии.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.dependencies import CurrentUserDep
from backend.utils.http_clients import rag_client

knowledge_router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

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


@knowledge_router.get("/documents")
async def list_documents(current_user: CurrentUserDep):
    documents = await _fetch_documents_from_rag_service()
    return {"documents": documents, "collections": _COLLECTIONS}


# ЗАГЛУШКА — пишет в _DOCUMENTS, который list_documents никогда не читает (см. докстринг
# модуля). Реальный upload — presigned-URL-пайплайн, не подключён сюда.
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


# ЗАГЛУШКА — см. докстринг модуля и upload_document выше.
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
