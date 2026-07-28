from __future__ import annotations

import csv
from pathlib import Path

_DATASET_PATH = Path(__file__).parent.parent / "ml_router" / "data" / "dataset.csv"


def test_dataset_still_has_only_the_three_original_labels():
    """Трипваер: пока в датасете только 3 класса, ветки personal/complex в графе
    (lean_rag_agent.py) недостижимы живым трафиком - это и есть страховка безопасности
    для всего каркаса целевой архитектуры (см. ARCHITECTURE.md, план внедрения шаг 1c).
    Падение этого теста = сигнал "роутер переобучен с новыми классами, пора включать
    personal/complex по-настоящему", не баг.
    """
    with open(_DATASET_PATH, newline="", encoding="utf-8") as f:
        labels = {row["label"] for row in csv.DictReader(f)}

    assert labels == {"domain_rag", "smalltalk", "out_of_domain"}
