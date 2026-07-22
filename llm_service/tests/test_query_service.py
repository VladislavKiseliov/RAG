from __future__ import annotations

import pytest

from llm_service.application.services.query_service import QueryExpansionService


# ---------------------------------------------------------------------------
# QueryExpansionService.expand — статический метод
# ---------------------------------------------------------------------------

class TestQueryExpansionService:
    @pytest.mark.asyncio
    async def test_original_query_always_first(self):
        result = await QueryExpansionService.expand(
            original_query="исходный запрос",
            raw_query="вариант1\nвариант2",
        )
        assert result.queries[0] == "исходный запрос"

    @pytest.mark.asyncio
    async def test_llm_lines_added_after_original(self):
        result = await QueryExpansionService.expand(
            original_query="исходный",
            raw_query="вариант1\nвариант2\nвариант3",
        )
        assert "вариант1" in result.queries
        assert "вариант2" in result.queries
        assert "вариант3" in result.queries

    @pytest.mark.asyncio
    async def test_no_duplicates(self):
        result = await QueryExpansionService.expand(
            original_query="исходный запрос",
            raw_query="исходный запрос\nвариант2",
        )
        assert result.queries.count("исходный запрос") == 1

    @pytest.mark.asyncio
    async def test_max_queries_limit(self):
        raw_query = "\n".join(f"вариант{i}" for i in range(20))
        result = await QueryExpansionService.expand(
            original_query="исходный",
            raw_query=raw_query,
            max_queries=4,
        )
        assert len(result.queries) <= 4

    @pytest.mark.asyncio
    async def test_empty_row_query_returns_only_original(self):
        result = await QueryExpansionService.expand(
            original_query="исходный запрос",
            raw_query="",
        )
        assert result.queries == ["исходный запрос"]

    @pytest.mark.asyncio
    async def test_strips_bullet_prefixes(self):
        result = await QueryExpansionService.expand(
            original_query="исходный",
            raw_query="- вариант с тире\n• вариант с буллетом",
        )
        assert "вариант с тире" in result.queries
        assert "вариант с буллетом" in result.queries

    @pytest.mark.asyncio
    async def test_original_query_in_pack(self):
        result = await QueryExpansionService.expand(
            original_query="мой запрос",
            raw_query="вариант1",
        )
        assert result.original_query == "мой запрос"

    @pytest.mark.asyncio
    async def test_empty_lines_skipped(self):
        result = await QueryExpansionService.expand(
            original_query="исходный",
            raw_query="вариант1\n\n\nвариант2",
        )
        assert "" not in result.queries