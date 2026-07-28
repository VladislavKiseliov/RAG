from __future__ import annotations

import sys
import types
import logging
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Test-local logger stub - тот же паттерн, что в test_integration_upload_webhook_flow.py,
# чтобы не тянуть python-json-logger в юнит-тест.
if "rag_service.utils.logger_config" not in sys.modules:
    logger_stub = types.ModuleType("rag_service.utils.logger_config")

    def _setup_logger(name: str):
        return logging.getLogger(name)

    logger_stub.setup_logger = _setup_logger
    sys.modules["rag_service.utils.logger_config"] = logger_stub

from rag_service.api.schemas import DocumentStatus
from rag_service.application.task_dispatcher_service import (
    TaskDispatcherService,
    _is_ingestion_artifact,
)
from rag_service.domain.errors import DocumentByStorageKeyNotFound


DOC_ID = str(uuid.uuid4())


@pytest.mark.parametrize("s3key", [
    f"{DOC_ID}/full.md",
    f"{DOC_ID}/chapters/chapter_4_3.md",
    f"{DOC_ID}/chapters/chapter_78.md",
    f"{DOC_ID}/tables/table_1.csv",
    f"{DOC_ID}/tables/table_1.html",
    f"{DOC_ID}/meta/toc.md",
])
def test_recognizes_ingestion_artifacts(s3key):
    assert _is_ingestion_artifact(s3key) is True


@pytest.mark.parametrize("s3key", [
    f"{DOC_ID}/report.pdf",
    f"{DOC_ID}/some full.md.pdf",  # содержит "full.md" как подстроку имени, но не суффикс
    f"{DOC_ID}/annual_meta.pdf",
])
def test_does_not_flag_real_uploads_as_artifacts(s3key):
    assert _is_ingestion_artifact(s3key) is False


@pytest.mark.asyncio
async def test_dispatch_ingestion_ignores_artifact_keys_without_db_lookup():
    # Регрессия на найденный шум в логах: MinIO шлёт вебхук на каждую запись в бакет,
    # включая служебные артефакты, которые ingestion_service сам заливает обратно после
    # разбора документа - раньше это било в DocumentByStorageKeyNotFound на каждый
    # артефакт (до сотен ERROR-записей на документ с N главами).
    database = MagicMock()
    database.get_document_by_s3key = AsyncMock()
    service = TaskDispatcherService(database=database)

    await service.dispatch_ingestion(s3key=f"{DOC_ID}/chapters/chapter_1.md")

    database.get_document_by_s3key.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_ingestion_still_raises_for_genuinely_unknown_key():
    # Настоящий сбой (документ реально не найден в БД по НЕ-служебному s3key) должен
    # по-прежнему всплывать как ошибка, не проглатываться заодно с шумом.
    database = MagicMock()
    database.get_document_by_s3key = AsyncMock(return_value=None)
    service = TaskDispatcherService(database=database)

    with pytest.raises(DocumentByStorageKeyNotFound):
        await service.dispatch_ingestion(s3key=f"{DOC_ID}/report.pdf")


@pytest.mark.asyncio
async def test_dispatch_ingestion_skips_non_pending_document():
    doc = MagicMock(status=DocumentStatus.COMPLETED, id=DOC_ID)
    database = MagicMock()
    database.get_document_by_s3key = AsyncMock(return_value=doc)
    database.update_document = AsyncMock()
    service = TaskDispatcherService(database=database)

    await service.dispatch_ingestion(s3key=f"{DOC_ID}/report.pdf")

    database.update_document.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_ingestion_sends_task_by_name_for_pending_document():
    # Регрессия: раньше диспатч делал `from rag_service.workers.task import
    # ingest_document_task; ingest_document_task.delay(...)` - импорт этого модуля
    # тянет Docling/torch (см. rag_service/worker_container.py), которых нет в лёгком
    # образе rag-service. Теперь диспатч должен идти по имени задачи через
    # `celery_app.send_task`, не импортируя воркер-код вообще.
    doc = MagicMock(status=DocumentStatus.PENDING, id=DOC_ID)
    database = MagicMock()
    database.get_document_by_s3key = AsyncMock(return_value=doc)
    database.update_document = AsyncMock()
    service = TaskDispatcherService(database=database)
    s3key = f"{DOC_ID}/report.pdf"

    with patch("rag_service.application.task_dispatcher_service.celery_app") as mock_celery_app:
        await service.dispatch_ingestion(s3key=s3key)

    mock_celery_app.send_task.assert_called_once_with("ingest_document", args=[str(DOC_ID), s3key])