from __future__ import annotations

import sys
import types
import logging
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# Test-local logger stub - тот же паттерн, что в test_task_dispatcher_service.py,
# чтобы не тянуть python-json-logger в юнит-тест.
if "rag_service.utils.logger_config" not in sys.modules:
    logger_stub = types.ModuleType("rag_service.utils.logger_config")

    def _setup_logger(name: str):
        return logging.getLogger(name)

    logger_stub.setup_logger = _setup_logger
    sys.modules["rag_service.utils.logger_config"] = logger_stub

from rag_service.api.schemas import DocumentStatus
from rag_service.application.ingestion_service import IngestionResult, IngestionService


DOC_ID = uuid.uuid4()
S3KEY = f"{DOC_ID}/report.pdf"


@pytest.mark.asyncio
async def test_process_document_skips_ghost_record_without_raising():
    # Регрессия: документ мог быть удалён между постановкой задачи в очередь
    # (TaskDispatcherService видел его PENDING) и её разбором Celery-воркером.
    # Раньше это было ValueError, брошенным ДО блока классификации ошибок -
    # улетало прямо в общий `except Exception` в workers/task.py, который считал
    # это транзиентным сбоем и ретраил 3 раза по 60с, хотя строка никогда не
    # появится обратно.
    document_service = MagicMock()
    document_service.get_document_by_id = AsyncMock(return_value=None)
    document_service.update_document = AsyncMock()

    service = IngestionService(
        document_service=document_service,
        vector_storage=MagicMock(),
        vector_indexing_service=MagicMock(),
        s3_storage=MagicMock(),
        conversion_pipeline=MagicMock(),
    )

    result = await service.process_document(doc_id=DOC_ID, s3key=S3KEY)

    assert result == IngestionResult(doc_id=DOC_ID, status=DocumentStatus.ERROR)
    document_service.update_document.assert_not_called()