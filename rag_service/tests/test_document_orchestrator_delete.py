from __future__ import annotations

import sys
import types
import logging
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# Test-local logger stub - тот же паттерн, что в других тестах rag_service (test_task_dispatcher_service.py,
# test_integration_upload_webhook_flow.py), чтобы не тянуть python-json-logger в юнит-тест.
if "rag_service.utils.logger_config" not in sys.modules:
    logger_stub = types.ModuleType("rag_service.utils.logger_config")

    def _setup_logger(name: str):
        return logging.getLogger(name)

    logger_stub.setup_logger = _setup_logger
    sys.modules["rag_service.utils.logger_config"] = logger_stub

from rag_service.application.document_orchestrator import DocumentOrchestrator
from rag_service.domain.errors.storage import StorageNotFoundError


DOC_ID = uuid.uuid4()
S3KEY = f"{DOC_ID}/report.pdf"


def make_orchestrator(*, document, stat_side_effect=None):
    s3_storage = MagicMock()
    s3_storage.stat = AsyncMock(side_effect=stat_side_effect)
    s3_storage.delete_file = AsyncMock()

    vector_storage = MagicMock()
    vector_storage.delete_by_field = AsyncMock()

    database = MagicMock()
    database.get_document_by_id = AsyncMock(return_value=document)
    database.delete_document = AsyncMock()

    orchestrator = DocumentOrchestrator(
        s3_storage=s3_storage, vector_storage=vector_storage, database=database,
    )
    return orchestrator, s3_storage, vector_storage, database


@pytest.mark.asyncio
async def test_delete_document_removes_file_when_present():
    document = MagicMock(s3key=S3KEY)
    orchestrator, s3_storage, vector_storage, database = make_orchestrator(document=document)

    await orchestrator.delete_document(DOC_ID)

    s3_storage.delete_file.assert_awaited_once_with(S3KEY)
    vector_storage.delete_by_field.assert_awaited_once_with("doc_id", str(DOC_ID))
    database.delete_document.assert_awaited_once_with(DOC_ID)


@pytest.mark.asyncio
async def test_delete_document_succeeds_when_file_already_missing_from_storage():
    # Регрессия: файл может пропасть из S3 не по вине самого документа (кто-то
    # вручную почистил бакет, миграция и т.п.) - раньше это ПОЛНОСТЬЮ блокировало
    # удаление (stat() падал -> ValueError -> 404 наружу через rag_routes.py), запись
    # в Postgres/Qdrant оставалась "осиротевшей" навсегда, без способа её убрать через UI.
    document = MagicMock(s3key=S3KEY)
    orchestrator, s3_storage, vector_storage, database = make_orchestrator(
        document=document, stat_side_effect=StorageNotFoundError("not found"),
    )

    await orchestrator.delete_document(DOC_ID)  # не должно бросить исключение

    s3_storage.delete_file.assert_not_called()  # нечего удалять - файла и так нет
    vector_storage.delete_by_field.assert_awaited_once_with("doc_id", str(DOC_ID))
    database.delete_document.assert_awaited_once_with(DOC_ID)


@pytest.mark.asyncio
async def test_delete_document_raises_for_unknown_document():
    orchestrator, _s3, _vec, _db = make_orchestrator(document=None)

    with pytest.raises(ValueError):
        await orchestrator.delete_document(DOC_ID)