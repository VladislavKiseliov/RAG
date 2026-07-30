"""Сравнение двух прогонов eval/run_eval.py по последнему runs/*.json на каждый experiment.

Запуск (внутри контейнера llm_service):
    python -m llm_service.eval.compare baseline no_rerank
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

_RUNS_DIR = Path(__file__).parent / "runs"
_DEFAULT_METRIC = "rerank_hit@5"


def find_latest_run(experiment_name: str, runs_dir: Path = _RUNS_DIR) -> dict:
    matches = sorted(runs_dir.glob(f"*_{experiment_name}.json"))
    if not matches:
        raise FileNotFoundError(f"нет прогонов для experiment={experiment_name!r} в {runs_dir}")
    return json.loads(matches[-1].read_text(encoding="utf-8"))


def check_comparable(run_a: dict, run_b: dict) -> list[str]:
    """Возвращает список проблем (пусто - можно сравнивать).

    Дешёвая проверка вместо полного provenance (git commit/corpus hash - это фаза E1):
    сверяет только, что оба прогона считались по одному и тому же набору вопросов.
    """
    ids_a = {r["id"] for r in run_a["per_question"]}
    ids_b = {r["id"] for r in run_b["per_question"]}
    problems = []
    if ids_a != ids_b:
        diff = sorted(ids_a ^ ids_b)
        problems.append(
            f"наборы вопросов не совпадают: {len(ids_a)} vs {len(ids_b)}, разница: {diff[:5]}..."
        )
    return problems


def aggregate_delta(run_a: dict, run_b: dict) -> dict[str, tuple[float, float, float]]:
    """{metric: (a_value, b_value, b-a)} по объединению ключей aggregate обоих прогонов."""
    keys = sorted(set(run_a["aggregate"]) | set(run_b["aggregate"]))
    out: dict[str, tuple[float, float, float]] = {}
    for key in keys:
        a_val = run_a["aggregate"].get(key)
        b_val = run_b["aggregate"].get(key)
        if a_val is None or b_val is None:
            continue
        out[key] = (a_val, b_val, b_val - a_val)
    return out


def per_question_flips(run_a: dict, run_b: dict, metric: str = _DEFAULT_METRIC) -> list[dict]:
    """Вопросы, где булева метрика metric поменяла значение между A и B."""
    by_id_a = {r["id"]: r for r in run_a["per_question"]}
    by_id_b = {r["id"]: r for r in run_b["per_question"]}
    flips = []
    for qid, row_a in by_id_a.items():
        row_b = by_id_b.get(qid)
        if row_b is None or metric not in row_a or metric not in row_b:
            continue
        if row_a[metric] != row_b[metric]:
            flips.append({"id": qid, "question": row_a["question"], "a": row_a[metric], "b": row_b[metric]})
    return flips


def sign_test_counts(run_a: dict, run_b: dict, metric: str = _DEFAULT_METRIC) -> dict[str, int]:
    by_id_a = {r["id"]: r for r in run_a["per_question"]}
    by_id_b = {r["id"]: r for r in run_b["per_question"]}
    better = worse = tied = 0
    for qid, row_a in by_id_a.items():
        row_b = by_id_b.get(qid)
        if row_b is None or metric not in row_a or metric not in row_b:
            continue
        if row_b[metric] > row_a[metric]:
            better += 1
        elif row_b[metric] < row_a[metric]:
            worse += 1
        else:
            tied += 1
    return {"better": better, "worse": worse, "tied": tied}


def print_comparison(name_a: str, run_a: dict, name_b: str, run_b: dict, metric: str = _DEFAULT_METRIC) -> None:
    problems = check_comparable(run_a, run_b)
    if problems:
        print("ВНИМАНИЕ: прогоны могут быть несравнимы:")
        for problem in problems:
            print(f"  - {problem}")
        print()

    print(f"=== {name_a} ({run_a['timestamp']}) vs {name_b} ({run_b['timestamp']}) ===\n")
    print("--- дельта агрегата (B - A) ---")
    for key, (a_val, b_val, delta) in aggregate_delta(run_a, run_b).items():
        sign = "+" if delta >= 0 else ""
        print(f"{key}: {a_val:.3f} -> {b_val:.3f}  ({sign}{delta:.3f})")

    print(f"\n--- {metric}: победы/поражения по вопросам ---")
    counts = sign_test_counts(run_a, run_b, metric)
    print(f"B лучше на {counts['better']}, хуже на {counts['worse']}, без изменений на {counts['tied']}")

    flips = per_question_flips(run_a, run_b, metric)
    if flips:
        print(f"\nсменившие результат вопросы ({metric}):")
        for flip in flips:
            print(f"  [{flip['id']}] {flip['a']} -> {flip['b']}  {flip['question']}")
    else:
        print("\nни один вопрос не сменил результат")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment_a")
    parser.add_argument("experiment_b")
    parser.add_argument("--metric", default=_DEFAULT_METRIC, help="Метрика для победы/поражения по вопросам")
    args = parser.parse_args()

    run_a_data = find_latest_run(args.experiment_a)
    run_b_data = find_latest_run(args.experiment_b)
    print_comparison(args.experiment_a, run_a_data, args.experiment_b, run_b_data, metric=args.metric)
