## Purpose
Admin-panel proxy over rag_service's document catalog: list/detail/delete/reindex/summarize/download, including bulk operations.

## Requirements

### Requirement: Upstream error translation
Errors returned by rag_service MUST be translated into a message the frontend can render directly, not passed through as an opaque object.

#### Scenario: rag_service returns a structured error
- **WHEN** a proxied request to rag_service fails with an error body containing a `message` field
- **THEN** the backend re-raises an `HTTPException` whose detail is that message string, not the raw JSON object

### Requirement: Isolated bulk operation failures
Bulk reindex/summarize MUST dispatch per-document concurrently and isolate failures so one bad document does not abort the batch.

#### Scenario: One document in a bulk reindex fails
- **WHEN** an admin triggers bulk reindex over 10 documents and one of them fails
- **THEN** the other 9 documents are still reindexed and the failure is reported only for the failing document

### Requirement: Download resolves storage key before streaming
Document download MUST fetch document detail first to resolve the storage key, and fail cleanly if the key is missing.

#### Scenario: Download a document whose file is missing
- **WHEN** an admin downloads a document whose `s3key` cannot be resolved
- **THEN** the response is 404, not a stream of empty/broken bytes
