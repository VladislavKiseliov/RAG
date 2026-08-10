## Purpose
LLM-judged sufficiency check that decides whether to answer with what's been retrieved, search again, or refuse.

## Requirements

### Requirement: Grey-zone trigger only
Reflection MUST only be triggered when the top rerank score falls in a configured grey zone between the no-data and confident thresholds, or when retrieval returned nothing.

#### Scenario: Top rerank score is clearly above the confident threshold
- **WHEN** the best reranked result scores above `rerank_grey_zone_threshold`
- **THEN** reflection is skipped and the answer proceeds directly with the retrieved data

### Requirement: Single reflect round maximum
The system MUST allow at most one reflect round; a second grey-zone result after a reflect round MUST force a terminal verdict instead of looping again.

#### Scenario: A second retrieval round is still in the grey zone
- **WHEN** reflection has already run once for this query and the new results are still ambiguous
- **THEN** a terminal verdict (sufficient/not_in_corpus) is forced rather than triggering another round

### Requirement: Verdict fallback on LLM failure
If the reflection LLM call fails or returns unparseable output, the verdict MUST be derived deterministically from whether any results were retrieved at all, not left unresolved.

#### Scenario: The reflection LLM call errors
- **WHEN** the reflect LLM call fails
- **THEN** the verdict falls back to `sufficient` if results exist or `not_in_corpus` if they don't, rather than crashing the request

### Requirement: Appendix need is signaled independently of the main verdict
Reflection MUST be able to independently flag that an appendix lookup is needed, resolved from the top retrieval item's document id rather than an LLM-guessed identifier.

#### Scenario: The query seems to reference an appendix
- **WHEN** reflection determines an appendix may be needed
- **THEN** the appendix is fetched using the `doc_id` of the top retrieved item, not a document id invented by the LLM
