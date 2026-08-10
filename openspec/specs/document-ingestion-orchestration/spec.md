## Purpose
Coordinates the full ingestion pipeline end-to-end and manages document status transitions with a defined error-handling policy.

## Requirements

### Requirement: Strict status state machine
Document status MUST transition strictly through PENDING→PROCESSING→EXTRACTING→INDEXING→COMPLETED; any out-of-order transition MUST be rejected.

#### Scenario: Attempting to skip a state
- **WHEN** code attempts to move a document directly from PENDING to INDEXING
- **THEN** an `InvalidIngestionStateError` is raised and the status is unchanged

### Requirement: Content-hash based duplicate detection
After download, the file's SHA-256 hash MUST be checked against existing documents; a duplicate MUST be deleted (DB row and S3 file) without retry.

#### Scenario: Uploading a byte-identical file under a different name
- **WHEN** ingestion computes a SHA-256 hash matching an already-ingested document
- **THEN** the new document's DB row and S3 file are deleted, and the task does not retry

### Requirement: Retry policy distinguishes transient from deterministic errors
Transient infrastructure errors (S3/Qdrant/DB operational errors) MUST propagate for Celery retry (max 3 retries); deterministic errors (validation, invalid state) MUST mark the document as ERROR without retrying.

#### Scenario: Qdrant is temporarily unreachable during indexing
- **WHEN** the vector store raises an operational/connection error mid-ingestion
- **THEN** the Celery task retries (up to 3 times, 60s countdown) rather than marking the document as permanently failed

#### Scenario: The uploaded file fails magic-byte validation
- **WHEN** downloaded file bytes don't match the expected format signature for its extension
- **THEN** the document is marked ERROR immediately, with no retry

### Requirement: Idempotent reindexing via vector cleanup
Before indexing, any existing vectors for the document MUST be deleted first, so reindexing the same document doesn't leave duplicate vectors.

#### Scenario: An already-indexed document is reindexed
- **WHEN** a document that was previously indexed is reindexed
- **THEN** its old vectors are deleted before the new ones are inserted, leaving no duplicates
