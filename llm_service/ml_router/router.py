from __future__ import annotations

from typing import Literal


class MLQueryRouter:
    def __init__(self, clf, embedder, confidence_threshold: float = 0.6) -> None:
        self.clf = clf
        self.embedder = embedder
        self.confidence_threshold = confidence_threshold

    def route(self, query: str) -> Literal["smalltalk", "domain_rag", "out_of_domain"]:
        vec = self.embedder.encode([query], normalize_embeddings=True)
        proba = self.clf.predict_proba(vec)[0]
        confidence = proba.max()

        if confidence < self.confidence_threshold:
            return "domain_rag"

        label: str = self.clf.classes_[proba.argmax()]
        return label  # type: ignore[return-value]