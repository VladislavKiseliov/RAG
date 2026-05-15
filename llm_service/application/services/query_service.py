from __future__ import annotations

from typing import Literal

from llm_service.application.lean_rag_models import ExpandedQueryPack



class MLQueryRouter:
    def __init__(self, clf, embedder, confidence_threshold: float = 0.5) -> None:
        self.clf = clf
        self.embedder = embedder
        embedder.encode(["warmup"], normalize_embeddings=True)  # прогрев
        self.confidence_threshold = confidence_threshold

    def route(self, query: str) -> Literal["smalltalk", "domain_rag", "out_of_domain"]:
        vec = self.embedder.encode([query], normalize_embeddings=True)
        proba = self.clf.predict_proba(vec)[0]
        confidence = proba.max()

        if confidence < self.confidence_threshold:
            return "domain_rag"

        label = self.clf.classes_[proba.argmax()]
        return label

class QueryExpansionService:

    @staticmethod
    async def expand(original_query: str, row_query: str, max_queries: int = 6) -> ExpandedQueryPack:

        raw_expansion = row_query.strip()
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
