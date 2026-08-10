## Purpose
Reranks rag_service search hits via a TEI cross-encoder before they are used for sufficiency judgment and answer generation.

## Requirements

### Requirement: Rerank by best child score per parent
Reranking MUST score each parent chunk by its best-scoring child chunk, not by concatenating or averaging across all of a parent's children.

#### Scenario: A parent has multiple child chunks of varying relevance
- **WHEN** reranking a parent with several children
- **THEN** the parent's rerank score is the best score among its children, not an average

### Requirement: Rerank query matches the latest plan formulation
The reranker MUST use the latest plan's query formulation, not the raw original user query and not a concatenation of multiple reformulations.
Rationale: a prior live bug caused a mismatch between the rerank query and retrieval query, producing a near-zero score (0.004) for content that should have scored ~0.85.

#### Scenario: The plan reformulates the user's original query
- **WHEN** reranking runs after a plan step reformulated the query
- **THEN** the rerank call uses that reformulated query text, not the user's original raw input

### Requirement: Truncation to final k after reranking
The reranked result set MUST be truncated to `rerank_final_k` after scoring, since the candidate pool may have doubled after a reflect round added more results.

#### Scenario: A reflect round has added extra candidates before rerank
- **WHEN** the retrieval pool contains more than `rerank_final_k` candidates after a reflect-triggered second round
- **THEN** only the top `rerank_final_k` results survive reranking

### Requirement: Empty input short-circuits without a network call
Reranking MUST skip the TEI network call entirely if there is no retrieval data to rerank.

#### Scenario: No documents were retrieved
- **WHEN** the retrieval step returns zero results
- **THEN** the rerank step does not make a network call to the TEI reranker
