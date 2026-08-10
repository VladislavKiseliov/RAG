## Purpose
Offline retrieval/rerank quality harness. Currently covers only retrieval-stage metrics (E0/E1); router (E2) and generation-faithfulness (E3) suites are documented in EVAL_PLAN.md but not implemented.

## Requirements

### Requirement: Retrieval metrics computed per run
Each eval run MUST compute `recall_at_k`, `hit_at_k`, `mrr`, `anchor_hit`, and `negative_precision` against a fixed question dataset.

#### Scenario: An eval run completes against the retrieval dataset
- **WHEN** `run_eval.py` finishes a retrieval-suite run
- **THEN** the run's results include all five metrics, persisted to `eval/runs/<timestamp>_<name>.json`

### Requirement: Negative precision as an honesty check
`negative_precision` MUST measure whether questions with no relevant document (or a below-threshold top score) are correctly identified as having no results.

#### Scenario: A question in the dataset has no correct document in the corpus
- **WHEN** evaluating a question tagged as having no valid answer in the corpus
- **THEN** `negative_precision` credits the run only if retrieval returned nothing or scored below `rerank_no_data_threshold`

### Requirement: Comparable-run guard in compare.py
Comparing two experiment runs MUST verify both runs used the identical question-ID set before computing a delta; mismatched sets MUST NOT produce a silently misleading comparison.

#### Scenario: Comparing two runs from different dataset versions
- **WHEN** `compare.py` is run against two eval runs whose question IDs don't fully overlap
- **THEN** the comparison is flagged as not directly comparable rather than silently computing a delta over a partial overlap
