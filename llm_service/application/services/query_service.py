from __future__ import annotations

import json

from llm_service.application.lean_rag_models import ExpandedQueryPack


class QueryExpansionService:

    @staticmethod
    async def expand(original_query: str, raw_query: str, max_queries: int = 6) -> ExpandedQueryPack:

        raw_expansion = raw_query.strip()

        try:
            parsed = json.loads(raw_expansion)
            expansion_lines = [str(item).strip() for item in parsed if str(item).strip()]
        except (json.JSONDecodeError, TypeError):
            expansion_lines = [line.strip("-• \t") for line in raw_expansion.splitlines() if line.strip()]

        queries = [original_query]
        for line in expansion_lines:
            if line and line not in queries:
                queries.append(line)
            if len(queries) >= max_queries:
                break

        return ExpandedQueryPack(
            original_query=original_query,
            queries=queries,
        )
