import asyncio
import uuid

import httpx

from rag_service.celery_app import celery_app
from rag_service.domain.chunking.chunk_builder import ParentChunk
from rag_service.domain.models.vector_point import VectorPoint
from rag_service.settings import settings
from rag_service.utils.logger_config import setup_logger
from rag_service.worker_container import build_worker_infrastructure, WorkerContainer

logger = setup_logger(__name__)


@celery_app.task(name="ingest_document", bind=True, max_retries=3)
def ingest_document_task(self, doc_id: str, s3key: str):
    logger.info("Celery received ingestion task doc_id=%s", doc_id)

    with asyncio.Runner() as runner:
        container = runner.run(build_worker_infrastructure())
        _doc_id = uuid.UUID(doc_id)
        try:
            runner.run(container.ingestion_service.process_document(doc_id=_doc_id, s3key=s3key))
        except Exception as exc:
            # process_document() уже сам обработал детерминированные и неизвестные
            # ошибки внутри (статус ERROR + заглушка отложенной очистки) — сюда
            # долетают только транзиентные инфраструктурные сбои (S3/Qdrant/БД),
            # которые имеет смысл ретраить.
            logger.warning("Transient ingestion error doc_id=%s, retrying: %s", doc_id, exc)
            raise self.retry(exc=exc, countdown=60)

    # Саммари глав — второстепенное дополнение поверх готового документа, не часть
    # критического пути индексации. Отдельная таска: падение/задержка LLM не должно
    # ни блокировать, ни ретраить сам ingest_document.
    if settings.enable_document_summarization:
        summarize_document_chapters_task.delay(doc_id)
    else:
        logger.info("Chapter summarization disabled (ENABLE_DOCUMENT_SUMMARIZATION=false), skipping doc_id=%s", doc_id)


async def _post_summary_request(path: str, payload: dict, *, log_label: str) -> str | None:
    """Общий best-effort POST в llm_service для саммари главы/документа/таблицы.

    Раньше это было три идентичные копии httpx-клиента и except-блока (T20 в
    rag_service/ISSUES.md) — различались только URL/payload/лейблом в логе.
    None при любой HTTP-ошибке — сбой одного элемента не должен ронять обработку
    остальных (см. цикл по главам/таблицам в summarize_document_chapters_task).
    """
    url = f"{settings.llm_service_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("summary")
    except (httpx.HTTPError, ValueError, AttributeError):
        # httpx.HTTPError - сеть/таймаут/4xx-5xx. ValueError - response.json() на теле,
        # которое не парсится как JSON (json.JSONDecodeError - подкласс ValueError).
        # AttributeError - валидный JSON, но не dict (.get() на списке/строке). Раньше
        # ловился только httpx.HTTPError - битый ответ llm_service падал бы наружу и
        # обрывал весь summarize_document_chapters_task (max_retries=0, без per-item
        # try/except в вызывающем цикле), теряя саммари всех оставшихся глав/таблиц
        # документа, а не только текущего элемента - вопреки собственному контракту
        # "best-effort, сбой одного элемента не должен ронять остальные".
        logger.warning("%s request failed, skipping", log_label, exc_info=True)
        return None


async def _summarize_chapter(chapter_text: str) -> str | None:
    """Best-effort запрос саммари главы в llm_service. None при любой ошибке."""
    return await _post_summary_request(
        "/llm/chapter-summary", {"chapter_text": chapter_text}, log_label="Chapter summary",
    )


async def _summarize_document(chapter_summaries: str) -> str | None:
    """Best-effort синтез саммари документа из уже готовых саммари глав. None при ошибке."""
    return await _post_summary_request(
        "/llm/document-summary", {"chapter_summaries": chapter_summaries}, log_label="Document summary",
    )


async def _summarize_table(table_text: str) -> str | None:
    """Best-effort запрос описания таблицы в llm_service. None при любой ошибке.

    В отличие от саммари главы/документа, этот текст не для показа пользователю —
    он эмбеддится и уходит в Qdrant, см. _index_table_summary().
    """
    return await _post_summary_request(
        "/llm/table-summary", {"table_text": table_text}, log_label="Table summary",
    )


# Safety net поверх лимита промпта на длину саммари (ai_config.toml:
# table_summary_system_prompt) - LLM иногда всё равно превышает лимит на большой/плотной
# таблице (живой прогон: 9-строчная таблица дала ~2000 символов и TEI ответил 413
# Payload Too Large, уронив всю таску без этого предела).
_MAX_TABLE_SUMMARY_EMBED_CHARS = 1500


async def _index_table_summary(
    container: WorkerContainer, *, doc_id: uuid.UUID, table_index: int, summary: str, source: str
) -> uuid.UUID | None:
    """Кладёт саммари таблицы в Qdrant отдельной точкой поверх маркера `[→ Таблица N]`.

    Parent-текст — сам маркер, не саммари: `retrieve_service._resolve_tables_in_items`
    уже умеет разворачивать его в полную Markdown-таблицу при выдаче (тот же маркер,
    что вставляет _LinkingTableSerializer в markdown главы), так что показ пользователю
    не меняется. Эмбеддится при этом само саммари — оно и должно матчиться на
    семантический поиск, а не бессмысленный для эмбеддинга маркер.

    Best-effort, как и _summarize_table/_summarize_chapter: сбой здесь (TEI/Qdrant/БД)
    не должен ронять обработку остальных таблиц документа.

    Returns:
        Id созданной строки parent_chunks (для document_tables.parent_chunk_id — вызывающий
        код использует его как отметку "уже проиндексирована", см. summarize_document_chapters_task)
        или None при сбое.
    """
    embed_text = summary[:_MAX_TABLE_SUMMARY_EMBED_CHARS]

    try:
        parent = ParentChunk.create(
            text=f"[→ Таблица {table_index}](table_{table_index})",
            headers={"title": f"Таблица {table_index}", "table_index": table_index},
            source=source,
        )
        await container.document_service.add_parent_chunks(doc_id, [parent])

        dense_vectors, sparse_vectors = await container.v_indexing_service.get_hybrid_vectors([embed_text])
        point = VectorPoint(
            id=str(uuid.uuid4()),
            dense_vector=dense_vectors[0],
            sparse_vector=sparse_vectors[0],
            text=embed_text,
            payload={
                "parent_id": str(parent.id),
                "headers": parent.headers,
                "text": embed_text,
                "source": source,
                "doc_id": str(doc_id),
            },
        )
        await container.vector_storage.upsert_vectors([point])
        return parent.id
    except Exception:
        logger.warning(
            "Table summary indexing failed, skipping doc_id=%s table_index=%s",
            doc_id, table_index, exc_info=True,
        )
        return None


@celery_app.task(name="summarize_document_chapters", bind=True, max_retries=0)
def summarize_document_chapters_task(self, doc_id: str):
    """Гонит главы уже проиндексированного документа через llm_service по одной, пишет summary,
    затем синтезирует из них одно саммари документа. Тем же проходом гонит таблицы: пишет
    document_tables.summary и индексирует саммари в Qdrant отдельной точкой (см.
    _index_table_summary) — иначе содержимое таблиц невидимо для семантического поиска.

    Отдельная таска от ingest_document (см. её конец) — тот же Celery-воркер (solo pool)
    обрабатывает задачи по одной, так что главы и так уйдут в llm_service строго по очереди,
    без отдельной очереди/брокера под это. Идемпотентна для саммари (перезаписывает, не
    накапливает) и для индексации таблиц — таблицы с уже проставленным parent_chunk_id
    (т.е. уже есть точка в Qdrant) пропускаются, повторный запуск не плодит дубли.
    """
    logger.info("Celery received chapter summarization task doc_id=%s", doc_id)

    with asyncio.Runner() as runner:
        container = runner.run(build_worker_infrastructure())
        _doc_id = uuid.UUID(doc_id)
        chapters = runner.run(container.document_service.get_chapters_by_doc_id(_doc_id))

        chapter_summaries: list[str] = []
        for chapter in chapters:
            text = runner.run(container.s3_storage.get_file(chapter.s3_md_path)).decode("utf-8")
            summary = runner.run(_summarize_chapter(text))
            if summary:
                runner.run(container.document_service.update_chapter_summary(chapter.id, summary))
                chapter_summaries.append(f'Глава "{chapter.title}": {summary}')

        if chapter_summaries:
            doc_summary = runner.run(_summarize_document("\n\n".join(chapter_summaries)))
            if doc_summary:
                runner.run(container.document_service.update_document_summary(_doc_id, doc_summary))

        tables = runner.run(container.document_service.get_tables_by_doc_id(_doc_id))
        if tables:
            document = runner.run(container.document_service.get_document_by_id(_doc_id))
            doc_filename = document.filename if document else ""
            for table in tables:
                if table.parent_chunk_id is not None:
                    continue  # уже проиндексирована в Qdrant, повторный запуск не дублирует

                csv_text = runner.run(container.s3_storage.get_file(table.s3_csv_path)).decode("utf-8")
                summary = runner.run(_summarize_table(csv_text))
                if not summary:
                    continue
                runner.run(container.document_service.update_table_summary(table.id, summary))
                parent_chunk_id = runner.run(_index_table_summary(
                    container,
                    doc_id=_doc_id,
                    table_index=table.table_index,
                    summary=summary,
                    source=doc_filename,
                ))
                if parent_chunk_id is not None:
                    runner.run(container.document_service.update_table_parent_chunk_id(table.id, parent_chunk_id))

    logger.info(
        "Chapter summarization finished doc_id=%s chapters=%d tables=%d",
        doc_id, len(chapters), len(tables),
    )


def _notify_backend_index_complete(note_id: str, *, note_status: str, chunk_count: int | None = None) -> None:
    """Best-effort callback into backend so it can persist chunk_count/status on its note row.

    backend owns the notes table; rag_service only vectorizes, so completion has to be
    pushed back across the service boundary instead of written directly.
    """
    url = f"{settings.backend_internal_url}/internal/notes/{note_id}/index-complete"
    payload = {"status": note_status}
    if chunk_count is not None:
        payload["chunk_count"] = chunk_count
    headers = {"Authorization": f"Bearer {settings.internal_webhook_token}"}
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(url, json=payload, headers=headers)
    except Exception:
        logger.exception("Failed to notify backend about note indexing result note_id=%s", note_id)


@celery_app.task(name="index_note", bind=True, max_retries=3)
def index_note_task(self, note_id: str, user_id: str, text: str):
    logger.info("Celery received note indexing task note_id=%s", note_id)

    from rag_service.application.note_vectorization_service import NoteVectorizationService

    with asyncio.Runner() as runner:
        container = runner.run(build_worker_infrastructure())
        service = NoteVectorizationService(
            vector_storage=container.notes_vector_storage,
            vector_indexing_service=container.v_indexing_service,
        )
        try:
            chunk_count = runner.run(service.index_note(uuid.UUID(note_id), user_id, text))
        except Exception as exc:
            logger.warning("Transient note indexing error note_id=%s, retrying: %s", note_id, exc)
            _notify_backend_index_complete(note_id, note_status="error")
            raise self.retry(exc=exc, countdown=30)

    _notify_backend_index_complete(note_id, note_status="indexed", chunk_count=chunk_count)