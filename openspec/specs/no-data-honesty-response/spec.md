## Purpose
Deterministic refusal path that avoids hallucinating an answer when context is weak or empty.

## Requirements

### Requirement: Fixed refusal bypasses generation
When the reflect gate verdict is `not_in_corpus`, the graph MUST route directly to a fixed refusal response and END, bypassing the generation node entirely.

#### Scenario: Reflection determines the corpus has no relevant information
- **WHEN** the reflect verdict is `not_in_corpus`
- **THEN** a fixed refusal message is returned without ever calling the generation LLM

### Requirement: Sources are cleared on refusal
Retrieval data MUST be cleared before returning a not-in-corpus refusal, so that source citations are never attached to a "not found" answer.

#### Scenario: A refusal is generated after some (insufficient) data was retrieved
- **WHEN** the no-data path is taken despite some retrieval data existing
- **THEN** the response includes no source citations
