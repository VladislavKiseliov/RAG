"""Тесты на e5-инструкционные префиксы (query: / passage:) в VectorIndexingService.

Отдельный файл от test_vector_indexing_service.py — тот тестирует API
(upsert_points/vector_provider), которого в текущем классе уже нет (сломан
независимо от этой задачи, см. rag_service/ISSUES.md).
"""

from unittest.mock import AsyncMock

import pytest

from rag_service.application.vector_indexing_service import VectorIndexingService


@pytest.fixture
def embedding_provider_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.embed = AsyncMock(side_effect=lambda texts: [[0.0] for _ in texts])
    return mock


@pytest.fixture
def indexing_service(embedding_provider_mock: AsyncMock) -> VectorIndexingService:
    return VectorIndexingService(
        embedding_provider=embedding_provider_mock,
        sparse_provider=AsyncMock(),
    )


class TestEmbedQueries:
    @pytest.mark.asyncio
    async def test_prefixes_each_text_with_query(
        self, indexing_service: VectorIndexingService, embedding_provider_mock: AsyncMock
    ) -> None:
        await indexing_service.embed_queries(["как настроить ПЛК", "давление в системе"])

        embedding_provider_mock.embed.assert_awaited_once_with(
            ["query: как настроить ПЛК", "query: давление в системе"]
        )

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty_without_calling_provider(
        self, indexing_service: VectorIndexingService, embedding_provider_mock: AsyncMock
    ) -> None:
        result = await indexing_service.embed_queries([])

        assert result == []
        embedding_provider_mock.embed.assert_not_called()


class TestEmbedPassages:
    @pytest.mark.asyncio
    async def test_prefixes_each_text_with_passage(
        self, indexing_service: VectorIndexingService, embedding_provider_mock: AsyncMock
    ) -> None:
        await indexing_service.embed_passages(["Глава 1. Общие положения", "Таблица допусков"])

        embedding_provider_mock.embed.assert_awaited_once_with(
            ["passage: Глава 1. Общие положения", "passage: Таблица допусков"]
        )

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty_without_calling_provider(
        self, indexing_service: VectorIndexingService, embedding_provider_mock: AsyncMock
    ) -> None:
        result = await indexing_service.embed_passages([])

        assert result == []
        embedding_provider_mock.embed.assert_not_called()


class TestPublicMethodsRouteToCorrectPrefix:
    """Существующие публичные методы не переименованы (чтобы не трогать вызывающий
    код в retrieve_service.py/ingestion_service.py), но обязаны использовать
    правильный префикс через embed_queries()/embed_passages()."""

    @pytest.mark.asyncio
    async def test_get_query_embedding_uses_query_prefix(
        self, indexing_service: VectorIndexingService, embedding_provider_mock: AsyncMock
    ) -> None:
        await indexing_service.get_query_embedding("температура насоса")

        embedding_provider_mock.embed.assert_awaited_once_with(["query: температура насоса"])

    @pytest.mark.asyncio
    async def test_get_embeddings_batch_uses_query_prefix(
        self, indexing_service: VectorIndexingService, embedding_provider_mock: AsyncMock
    ) -> None:
        await indexing_service.get_embeddings(["запрос 1", "запрос 2"])

        embedding_provider_mock.embed.assert_awaited_once_with(["query: запрос 1", "query: запрос 2"])

    @pytest.mark.asyncio
    async def test_get_dense_vectors_uses_passage_prefix(
        self, indexing_service: VectorIndexingService, embedding_provider_mock: AsyncMock
    ) -> None:
        await indexing_service.get_dense_vectors(["текст главы документа"])

        embedding_provider_mock.embed.assert_awaited_once_with(["passage: текст главы документа"])

    @pytest.mark.asyncio
    async def test_query_and_passage_prefixes_never_cross(
        self, indexing_service: VectorIndexingService, embedding_provider_mock: AsyncMock
    ) -> None:
        await indexing_service.get_query_embedding("запрос")
        query_call_args = embedding_provider_mock.embed.await_args_list[0].args[0]

        embedding_provider_mock.embed.reset_mock()

        await indexing_service.get_dense_vectors(["документ"])
        passage_call_args = embedding_provider_mock.embed.await_args_list[0].args[0]

        assert query_call_args[0].startswith("query: ")
        assert passage_call_args[0].startswith("passage: ")