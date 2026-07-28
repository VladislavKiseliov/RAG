from __future__ import annotations

import sys
import types
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

# Test-local logger stub - тот же паттерн, что в остальных юнит-тестах rag_service,
# чтобы не тянуть python-json-logger.
if "rag_service.utils.logger_config" not in sys.modules:
    logger_stub = types.ModuleType("rag_service.utils.logger_config")

    def _setup_logger(name: str):
        return logging.getLogger(name)

    logger_stub.setup_logger = _setup_logger
    sys.modules["rag_service.utils.logger_config"] = logger_stub

from rag_service.infrastructures.repositories.qdrant_vector_storage import QdrantVectorStorage


def make_storage():
    client = MagicMock()
    client.query_points = AsyncMock(return_value=MagicMock(points=[]))
    storage = QdrantVectorStorage(client=client, collection="test-collection")
    return storage, client


@pytest.mark.asyncio
async def test_search_passes_score_threshold_to_query_points():
    # Регрессия B3: search() принимал score_threshold как параметр, но не передавал
    # его в query_points() - в отличие от batch_search(), который делает это верно.
    # Любой вызывающий код (retrieve_service.py), полагающийся на отсечение по скору,
    # молча получал все top_k результатов независимо от релевантности.
    storage, client = make_storage()

    await storage.search(
        query_vector=[0.1, 0.2, 0.3],
        query_text="test query",
        top_k=5,
        score_threshold=0.75,
    )

    _, kwargs = client.query_points.call_args
    assert kwargs["score_threshold"] == 0.75


@pytest.mark.asyncio
async def test_search_passes_none_score_threshold_when_not_set():
    storage, client = make_storage()

    await storage.search(
        query_vector=[0.1, 0.2, 0.3],
        query_text="test query",
        top_k=5,
    )

    _, kwargs = client.query_points.call_args
    assert kwargs["score_threshold"] is None