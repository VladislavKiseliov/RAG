from __future__ import annotations

from llm_service.eval.compare import (
    aggregate_delta,
    check_comparable,
    per_question_flips,
    sign_test_counts,
)


def make_run(*, timestamp="2026-01-01T00-00-00", aggregate=None, per_question=None) -> dict:
    return {
        "timestamp": timestamp,
        "aggregate": aggregate or {},
        "per_question": per_question or [],
    }


class TestCheckComparable:
    def test_same_question_ids_is_comparable(self):
        run_a = make_run(per_question=[{"id": "q1"}, {"id": "q2"}])
        run_b = make_run(per_question=[{"id": "q1"}, {"id": "q2"}])
        assert check_comparable(run_a, run_b) == []

    def test_different_question_ids_reports_problem(self):
        run_a = make_run(per_question=[{"id": "q1"}, {"id": "q2"}])
        run_b = make_run(per_question=[{"id": "q1"}, {"id": "q3"}])
        problems = check_comparable(run_a, run_b)
        assert len(problems) == 1
        assert "не совпадают" in problems[0]


class TestAggregateDelta:
    def test_computes_delta_for_shared_keys(self):
        run_a = make_run(aggregate={"hit@5": 0.8})
        run_b = make_run(aggregate={"hit@5": 0.6})
        a_val, b_val, delta = aggregate_delta(run_a, run_b)["hit@5"]
        assert (a_val, b_val) == (0.8, 0.6)
        assert delta == b_val - a_val

    def test_skips_keys_missing_in_either_run(self):
        run_a = make_run(aggregate={"hit@5": 0.8, "only_a": 1.0})
        run_b = make_run(aggregate={"hit@5": 0.6, "only_b": 1.0})
        assert list(aggregate_delta(run_a, run_b).keys()) == ["hit@5"]


class TestPerQuestionFlips:
    def test_finds_metric_flip(self):
        run_a = make_run(per_question=[{"id": "q1", "question": "?", "hit@5": True}])
        run_b = make_run(per_question=[{"id": "q1", "question": "?", "hit@5": False}])
        flips = per_question_flips(run_a, run_b, metric="hit@5")
        assert flips == [{"id": "q1", "question": "?", "a": True, "b": False}]

    def test_no_flip_when_metric_unchanged(self):
        run_a = make_run(per_question=[{"id": "q1", "question": "?", "hit@5": True}])
        run_b = make_run(per_question=[{"id": "q1", "question": "?", "hit@5": True}])
        assert per_question_flips(run_a, run_b, metric="hit@5") == []


class TestSignTestCounts:
    def test_counts_better_worse_tied(self):
        run_a = make_run(per_question=[
            {"id": "q1", "hit@5": False},
            {"id": "q2", "hit@5": True},
            {"id": "q3", "hit@5": True},
        ])
        run_b = make_run(per_question=[
            {"id": "q1", "hit@5": True},
            {"id": "q2", "hit@5": False},
            {"id": "q3", "hit@5": True},
        ])
        assert sign_test_counts(run_a, run_b, metric="hit@5") == {"better": 1, "worse": 1, "tied": 1}
