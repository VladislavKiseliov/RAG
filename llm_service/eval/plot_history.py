"""Строит график метрик по всем прогонам eval/runs/*.json (см. run_eval.py::save_run).

Запуск (внутри контейнера llm_service):
    python -m llm_service.eval.plot_history
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # без дисплея - контейнер headless, график только в файл
import matplotlib.pyplot as plt

_RUNS_DIR = Path(__file__).parent / "runs"
_OUTPUT_PATH = _RUNS_DIR / "history.png"


def load_runs(runs_dir: Path = _RUNS_DIR) -> list[dict]:
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(runs_dir.glob("*.json"))]
    runs.sort(key=lambda run: run["timestamp"])
    return runs


def plot(runs: list[dict], output_path: Path = _OUTPUT_PATH) -> Path:
    labels = [f"{run['timestamp']}\n{run['name']}" for run in runs]

    fig, ax = plt.subplots(figsize=(max(6, len(runs) * 1.5), 5))
    metric_keys = [
        "candidate_recall@k_cand", "rerank_hit@5", "rerank_mrr@5", "rerank_anchor_hit@5",
        "negative_rejection_rate",
    ]
    for key in metric_keys:
        values = [run["aggregate"].get(key) for run in runs]
        if all(v is None for v in values):
            continue
        ax.plot(labels, values, marker="o", label=key)

    ax.set_ylim(0, 1.05)
    ax.set_ylabel("значение метрики (ближе к 1 - лучше)")
    ax.set_title("История прогонов eval/run_eval.py")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    fig.savefig(output_path)
    return output_path


if __name__ == "__main__":
    runs = load_runs()
    if not runs:
        print(f"Нет прогонов в {_RUNS_DIR} - сначала запустите run_eval.py")
    else:
        path = plot(runs)
        print(f"График сохранён: {path} ({len(runs)} прогонов)")
