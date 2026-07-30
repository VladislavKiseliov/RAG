"""E0/E1 (см. EVAL_PLAN.md): прогон retrieval.jsonl через rag_service + TEI-реранкер,
стадийные метрики (кандидаты до реранка / финальный топ). Переиспользует те же
клиенты (RetrievalService/RerankerService), что и боевой граф — не дублирует HTTP-логику.

Каждый прогон сохраняется в eval/runs/<timestamp>_<name>.json — история для plot_history.py.

Запуск (внутри контейнера llm_service, сеть уже видит rag-service/tei-reranker):
    python -m llm_service.eval.run_eval --name baseline
"""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from llm_service.ai_config import get_live_config
from llm_service.application.lean_rag_models import RetrieveItem
from llm_service.application.services.reranker_service import RerankerService
from llm_service.application.services.retrieval_service import RetrievalService
from llm_service.eval.suites.retrieval import (
    RankedItem,
    anchor_hit,
    hit_at_k,
    mrr,
    negative_precision,
    recall_at_k,
)
from llm_service.settings import settings

_DATASET_PATH = Path(__file__).parent / "datasets" / "retrieval.jsonl"
_QUICK_DATASET_PATH = Path(__file__).parent / "datasets" / "retrieval_quick.jsonl"
_RUNS_DIR = Path(__file__).parent / "runs"
_EXPERIMENTS_DIR = Path(__file__).parent / "experiments"
_CANDIDATE_K = 30
_FINAL_K = 5


@dataclass(frozen=True)
class ExperimentConfig:
    """Именованный набор настроек прогона — см. eval/experiments/*.yaml."""
    name: str
    rerank: bool = True
    top_k_candidates: int = _CANDIDATE_K
    final_k: int = _FINAL_K


def load_experiment(name: str) -> ExperimentConfig:
    path = _EXPERIMENTS_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"experiment config not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ExperimentConfig(
        name=raw.get("name", name),
        rerank=raw.get("rerank", True),
        top_k_candidates=raw.get("top_k_candidates", _CANDIDATE_K),
        final_k=raw.get("final_k", _FINAL_K),
    )


@dataclass
class Question:
    id: str
    category: str
    question: str
    doc_id: str | None
    expected_chapters: list[str]
    answer_anchor: str

    @property
    def is_negative(self) -> bool:
        """Вопрос считается негативным, если категория начинается с 'negative'
        или у него отсутствуют ожидаемые целевые документы/главы.
        """
        return self.category.startswith("negative") or (not self.doc_id and not self.expected_chapters)


def load_dataset(path: Path = _DATASET_PATH) -> list[Question]:
    questions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        questions.append(
            Question(
                id=raw["id"],
                category=raw["category"],
                question=raw["question"],
                doc_id=raw.get("doc_id"),
                expected_chapters=raw.get("expected_chapters", []),
                answer_anchor=raw.get("answer_anchor", ""),
            )
        )
    return questions


def _candidates_to_ranked(candidates: list[RetrieveItem]) -> list[RankedItem]:
    return [
        RankedItem(
            doc_id=item.metadata.doc_id,
            chapter_number=item.metadata.headers.get("chapter_number", ""),
            parent_chunk=item.parent_chunk,
            score=item.metadata.score,
        )
        for item in candidates
    ]


async def _rerank_to_ranked(
        reranker: RerankerService, query: str, candidates: list[RetrieveItem],
) -> list[RankedItem]:
    if not candidates:
        return []
    texts = [
        max(item.child_chunks, key=lambda c: c.score).text if item.child_chunks else item.parent_chunk
        for item in candidates
    ]
    scored = await reranker.rerank(query=query, texts=texts)
    return [
        RankedItem(
            doc_id=candidates[entry["index"]].metadata.doc_id,
            chapter_number=candidates[entry["index"]].metadata.headers.get("chapter_number", ""),
            parent_chunk=candidates[entry["index"]].parent_chunk,
            score=entry["score"],
        )
        for entry in scored
    ]


async def run(config: ExperimentConfig | None = None, dataset_path: Path = _DATASET_PATH) -> list[dict]:
    config = config or ExperimentConfig(name="baseline")
    questions = load_dataset(dataset_path)
    threshold = get_live_config().gateway.rerank_no_data_threshold

    retrieval = RetrievalService(base_url=settings.RAG_SERVICE_URL)
    reranker = RerankerService(base_url=settings.RERANKER_TEI_URL, timeout=settings.LLM_RERANK_TIMEOUT)

    results: list[dict] = []
    try:
        for q in questions:
            retrieved = await retrieval.retrieve(
                [q.question], top_k_per_query=config.top_k_candidates, max_parents=config.top_k_candidates,
            )
            candidates = _candidates_to_ranked(retrieved.items)
            if config.rerank:
                final = (await _rerank_to_ranked(reranker, q.question, retrieved.items))[:config.final_k]
            else:
                final = candidates[:config.final_k]

            row: dict = {
                "id": q.id,
                "category": q.category,
                "question": q.question,
                "is_negative": q.is_negative,
            }

            if q.is_negative:
                row["top_score"] = final[0].score if final else None
                row["negative_rejection_rate"] = negative_precision(final, threshold=threshold)
            else:
                row["expected_chapters"] = q.expected_chapters
                row["actual_chapters"] = [item.chapter_number for item in final]
                row["candidate_recall@k_cand"] = recall_at_k(
                    candidates, expected_doc_id=q.doc_id, expected_chapters=q.expected_chapters,
                    k=config.top_k_candidates,
                )
                row["rerank_hit@5"] = hit_at_k(
                    final, expected_doc_id=q.doc_id, expected_chapters=q.expected_chapters, k=config.final_k,
                )
                row["rerank_mrr@5"] = mrr(final, expected_doc_id=q.doc_id, expected_chapters=q.expected_chapters)
                row["rerank_anchor_hit@5"] = anchor_hit(
                    final, expected_doc_id=q.doc_id, anchor=q.answer_anchor, k=config.final_k,
                )
            results.append(row)
    finally:
        await retrieval.aclose()
        await reranker.aclose()

    return results


def _aggregate(results: list[dict]) -> dict:
    positive = [r for r in results if not r["is_negative"]]
    negative = [r for r in results if r["is_negative"]]

    aggregate: dict = {}
    if positive:
        aggregate["candidate_recall@k_cand"] = sum(r["candidate_recall@k_cand"] for r in positive) / len(positive)
        aggregate["rerank_hit@5"] = sum(r["rerank_hit@5"] for r in positive) / len(positive)
        aggregate["rerank_mrr@5"] = sum(r["rerank_mrr@5"] for r in positive) / len(positive)
        aggregate["rerank_anchor_hit@5"] = sum(r["rerank_anchor_hit@5"] for r in positive) / len(positive)
    if negative:
        aggregate["negative_rejection_rate"] = sum(r["negative_rejection_rate"] for r in negative) / len(negative)
    return aggregate


def _print_report(results: list[dict], aggregate: dict) -> None:
    for row in results:
        print(f"[{row['id']}] ({row['category']}) {row['question']}")
        if not row["is_negative"]:
            print(f"    ожидали: {row['expected_chapters']}")
            print(f"    нашли:   {row['actual_chapters']}")
        for key, value in row.items():
            if key in ("id", "category", "question", "is_negative", "expected_chapters", "actual_chapters"):
                continue
            print(f"    {key}: {value}")

    if aggregate:
        print("\n--- aggregate ---")
        for key, value in aggregate.items():
            print(f"{key}: {value:.2f}")


def save_run(results: list[dict], aggregate: dict, config: ExperimentConfig) -> Path:
    """Пишет прогон в eval/runs/<timestamp>_<name>.json - история для plot_history.py."""
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    path = _RUNS_DIR / f"{timestamp}_{config.name}.json"
    payload = {
        "name": config.name,
        "timestamp": timestamp,
        "config": {
            "rerank": config.rerank,
            "top_k_candidates": config.top_k_candidates,
            "final_k": config.final_k,
        },
        "aggregate": aggregate,
        "per_question": results,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiment", default=None, help="Имя конфига из eval/experiments/<name>.yaml",
    )
    parser.add_argument(
        "--name", default=None, help="Алиас --experiment (совместимость)",
    )
    parser.add_argument(
        "--dataset", choices=["full", "quick"], default="full",
        help="full = datasets/retrieval.jsonl (136), quick = datasets/retrieval_quick.jsonl (~50)",
    )
    args = parser.parse_args()

    experiment_config = load_experiment(args.experiment or args.name or "baseline")
    dataset_path = _QUICK_DATASET_PATH if args.dataset == "quick" else _DATASET_PATH

    results = asyncio.run(run(experiment_config, dataset_path))
    aggregate = _aggregate(results)
    _print_report(results, aggregate)

    saved_path = save_run(results, aggregate, experiment_config)
    print(f"\nсохранено: {saved_path}")