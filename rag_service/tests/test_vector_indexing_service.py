"""Тесты sparse- и гибридного пути VectorIndexingService.

Dense/passage-префиксы (embed_queries/embed_passages/get_dense_vectors) уже
покрыты в test_vector_indexing_prefixes.py — здесь только то, что не
пересекается: raw sparse-путь (без e5-префиксов) и параллельная сборка
гибридных векторов через get_hybrid_vectors().
"""

from unittest.mock import AsyncMock

import pytest

from rag_service.application.vector_indexing_service import VectorIndexingService
from rag_service.domain.models.vector_point import SparseVectorValue


@pytest.fixture
def embedding_provider_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.embed = AsyncMock()
    return mock


@pytest.fixture
def sparse_provider_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.get_sparse_embeddings = AsyncMock()
    return mock


@pytest.fixture
def indexing_service(embedding_provider_mock: AsyncMock, sparse_provider_mock: AsyncMock) -> VectorIndexingService:
    return VectorIndexingService(
        embedding_provider=embedding_provider_mock,
        sparse_provider=sparse_provider_mock,
    )


@pytest.mark.asyncio
async def test_get_sparse_vectors_returns_empty_for_empty_input(
    indexing_service: VectorIndexingService, sparse_provider_mock: AsyncMock
) -> None:
    result = await indexing_service.get_sparse_vectors([])

    assert result == []
    sparse_provider_mock.get_sparse_embeddings.assert_not_called()


@pytest.mark.asyncio
async def test_get_sparse_vectors_delegates_to_sparse_provider_without_prefix(
    indexing_service: VectorIndexingService, sparse_provider_mock: AsyncMock
) -> None:
    expected = [SparseVectorValue(indices=[1, 2], values=[0.1, 0.2])]
    sparse_provider_mock.get_sparse_embeddings.return_value = expected

    result = await indexing_service.get_sparse_vectors(["давление в системе"])

    sparse_provider_mock.get_sparse_embeddings.assert_awaited_once_with(["давление в системе"])
    assert result == expected


@pytest.mark.asyncio
async def test_get_hybrid_vectors_returns_passage_prefixed_dense_and_raw_sparse(
    indexing_service: VectorIndexingService,
    embedding_provider_mock: AsyncMock,
    sparse_provider_mock: AsyncMock,
) -> None:
    embedding_provider_mock.embed.return_value = [[0.1, 0.2]]
    sparse_provider_mock.get_sparse_embeddings.return_value = [SparseVectorValue(indices=[1], values=[0.9])]

    dense_vectors, sparse_vectors = await indexing_service.get_hybrid_vectors(["Глава 1. Общие положения"])

    embedding_provider_mock.embed.assert_awaited_once_with(["passage: Глава 1. Общие положения"])
    sparse_provider_mock.get_sparse_embeddings.assert_awaited_once_with(["Глава 1. Общие положения"])
    assert dense_vectors == [[0.1, 0.2]]
    assert sparse_vectors == [SparseVectorValue(indices=[1], values=[0.9])]


@pytest.mark.asyncio
async def test_get_hybrid_vectors_returns_empty_for_empty_input(
    indexing_service: VectorIndexingService,
    embedding_provider_mock: AsyncMock,
    sparse_provider_mock: AsyncMock,
) -> None:
    dense_vectors, sparse_vectors = await indexing_service.get_hybrid_vectors([])

    assert dense_vectors == []
    assert sparse_vectors == []
    embedding_provider_mock.embed.assert_not_called()
    sparse_provider_mock.get_sparse_embeddings.assert_not_called()
