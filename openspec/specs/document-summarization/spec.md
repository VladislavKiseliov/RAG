## Purpose
Best-effort chapter/document/table summarization via llm_service, run as a separate Celery task after ingestion.

## Requirements

### Requirement: Manual trigger bypasses the feature flag
Automatic post-ingest summarization MUST only run when `ENABLE_DOCUMENT_SUMMARIZATION=true`, but the manual API trigger MUST work regardless of that flag.

#### Scenario: Summarization is disabled by config
- **WHEN** `ENABLE_DOCUMENT_SUMMARIZATION` is false and a document finishes ingesting
- **THEN** no automatic summarization task runs, but calling `POST /documents/{id}/summarize` still triggers it

### Requirement: Per-item failure isolation
A failure summarizing one chapter or table MUST NOT abort summarization of the remaining chapters/tables in the same document.

#### Scenario: One chapter's summarization call errors
- **WHEN** the LLM call for one chapter's summary fails
- **THEN** that chapter is left without a summary, but other chapters and tables in the document are still summarized

### Requirement: Idempotent table summary indexing
A table whose summary has already been indexed (has a `parent_chunk_id` set) MUST be skipped on a rerun, not re-summarized and re-indexed.

#### Scenario: Summarization is rerun on an already-summarized document
- **WHEN** the summarization task runs again for a document whose tables already have summaries indexed
- **THEN** those tables are skipped, avoiding duplicate LLM calls and duplicate vector points

### Requirement: Table summary length capped before embedding
Table summaries MUST be truncated to a fixed character limit before being embedded, to stay under the embedding provider's request size limit.

#### Scenario: A table produces an unusually long summary
- **WHEN** an LLM-generated table summary exceeds 1500 characters
- **THEN** it is truncated to 1500 characters before being sent for embedding
