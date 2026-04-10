from unittest.mock import AsyncMock

import pytest

from rag_service.application.vector_indexing_service import VectorIndexingService


@pytest.fixture
def embedding_provider_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.embed = AsyncMock()
    return mock


@pytest.fixture
def vector_provider_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.upsert_vectors = AsyncMock()
    return mock


@pytest.fixture
def indexing_service(embedding_provider_mock: AsyncMock, vector_provider_mock: AsyncMock) -> VectorIndexingService:
    return VectorIndexingService(
        embedding_provider=embedding_provider_mock,
        vector_provider=vector_provider_mock,
        embedding_batch_size=2,
    )


@pytest.mark.asyncio
async def test_upsert_points_returns_for_empty_input(indexing_service: VectorIndexingService, embedding_provider_mock: AsyncMock, vector_provider_mock: AsyncMock) -> None:
    await indexing_service.upsert_points([])

    embedding_provider_mock.embed.assert_not_called()
    vector_provider_mock.upsert_vectors.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_points_raises_for_empty_text(indexing_service: VectorIndexingService) -> None:
    with pytest.raises(RuntimeError, match="Point text is empty"):
        await indexing_service.upsert_points([{"text": "   ", "payload": {}}])


@pytest.mark.asyncio
async def test_upsert_points_batches_embeddings_and_upserts_ready_vectors(
    indexing_service: VectorIndexingService,
    embedding_provider_mock: AsyncMock,
    vector_provider_mock: AsyncMock,
) -> None:
    embedding_provider_mock.embed.side_effect = [
        [[0.1, 0.2], [0.3, 0.4]],
        [[0.5, 0.6]],
    ]

    await indexing_service.upsert_points(
        [
            {"id": "a", "text": "alpha", "payload": {"x": 1}},
            {"id": "b", "text": "beta", "payload": {"x": 2}},
            {"id": "c", "text": "gamma", "payload": {}},
        ]
    )

    assert embedding_provider_mock.embed.await_count == 2
    embedding_provider_mock.embed.assert_any_await(["alpha", "beta"])
    embedding_provider_mock.embed.assert_any_await(["gamma"])
    vector_provider_mock.upsert_vectors.assert_awaited_once_with(
        [
            {"id": "a", "vector": [0.1, 0.2], "payload": {"x": 1, "text": "alpha"}},
            {"id": "b", "vector": [0.3, 0.4], "payload": {"x": 2, "text": "beta"}},
            {"id": "c", "vector": [0.5, 0.6], "payload": {"text": "gamma"}},
        ]
    )


@pytest.mark.asyncio
async def test_upsert_points_raises_when_embeddings_are_empty(
    indexing_service: VectorIndexingService,
    embedding_provider_mock: AsyncMock,
    vector_provider_mock: AsyncMock,
) -> None:
    embedding_provider_mock.embed.return_value = []

    with pytest.raises(RuntimeError, match="Embeddings are empty"):
        await indexing_service.upsert_points([{"id": "a", "text": "alpha", "payload": {}}])

    vector_provider_mock.upsert_vectors.assert_not_called()
