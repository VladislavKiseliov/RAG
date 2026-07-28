from __future__ import annotations

import sys
import types
import logging
import uuid
from unittest.mock import patch

import pytest

# Test-local logger stub - тот же паттерн, что в test_task_dispatcher_service.py,
# чтобы не тянуть python-json-logger в юнит-тест.
if "rag_service.utils.logger_config" not in sys.modules:
    logger_stub = types.ModuleType("rag_service.utils.logger_config")

    def _setup_logger(name: str):
        return logging.getLogger(name)

    logger_stub.setup_logger = _setup_logger
    sys.modules["rag_service.utils.logger_config"] = logger_stub

from rag_service.api.note_routes import index_note
from rag_service.api.schemas import NoteIndexRequest


@pytest.mark.asyncio
async def test_index_note_sends_task_by_name():
    # Регрессия: раньше маршрут делал `from rag_service.workers.task import
    # index_note_task; index_note_task.delay(...)` - импорт этого модуля тянет
    # Docling/torch (см. rag_service/worker_container.py), которых нет в лёгком
    # образе rag-service. Теперь диспатч должен идти по имени задачи через
    # `celery_app.send_task`, не импортируя воркер-код вообще.
    note_id = uuid.uuid4()
    payload = NoteIndexRequest(user_id="user-1", text="some note text")

    with patch("rag_service.api.note_routes.celery_app") as mock_celery_app:
        result = await index_note(note_id, payload)

    mock_celery_app.send_task.assert_called_once_with(
        "index_note", args=[str(note_id), payload.user_id, payload.text]
    )
    assert result == {"status": "queued"}