## Purpose
Receives MinIO `put` event notifications and turns them into Celery ingestion jobs, filtering out self-generated noise.

## Requirements

### Requirement: Bearer token required
The webhook endpoint MUST reject requests without a valid bearer token, compared in constant time.

#### Scenario: Webhook called without a valid token
- **WHEN** a request to the webhook endpoint is missing the correct `Authorization: Bearer` token
- **THEN** the request is rejected with 401 and no ingestion task is dispatched

### Requirement: Self-generated artifacts are filtered out
The webhook MUST ignore MinIO notification records whose object key matches ingestion's own output artifacts (chapters/tables/meta/full.md), to avoid re-triggering ingestion on its own output.

#### Scenario: Ingestion writes its own chapter markdown back to the bucket
- **WHEN** a MinIO notification arrives for a key under `{doc_id}/chapters/`
- **THEN** no new ingestion task is dispatched for that event

### Requirement: Idempotent dispatch by status
An ingestion task MUST only be dispatched if the document's current status is still PENDING.

#### Scenario: Webhook fires twice for the same upload (MinIO retry)
- **WHEN** two webhook notifications arrive for the same document, and the first has already advanced its status past PENDING
- **THEN** the second notification does not dispatch a duplicate ingestion task

### Requirement: Per-record failure isolation
A failure processing one notification record MUST NOT prevent processing of other records in the same webhook batch.

#### Scenario: One record in a batch is malformed
- **WHEN** a webhook payload contains multiple records and one fails to process
- **THEN** the other records are still processed, and MinIO does not retry the entire batch due to the one failure
