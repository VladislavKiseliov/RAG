## Purpose
Query/list/detail/delete/reindex operations over ingested documents, plus reader-facing content access to chapters, appendices, and parent chunks.

## Requirements

### Requirement: Best-effort S3 cleanup on delete
Deleting a document MUST clean up its database and vector-store records even if the underlying S3 file is already missing; it MUST also sweep all derived artifacts under the document's key prefix, not just the original file.

#### Scenario: Deleting a document whose S3 file was already removed out-of-band
- **WHEN** a document's DB record exists but its S3 file is missing, and it is deleted
- **THEN** the DB and vector records are removed without the missing-file error blocking cleanup

#### Scenario: Deleting a fully-ingested document
- **WHEN** a document with chapters/tables/meta artifacts is deleted
- **THEN** all objects under its `{doc_id}/` S3 prefix are removed, not only the original uploaded file

### Requirement: Reindex reuses idempotent ingestion
Reindexing a document MUST reuse the same ingestion pipeline (not a separate code path), relying on structural-data reset and vector delete-before-insert for idempotency.

#### Scenario: An admin triggers reindex on an already-completed document
- **WHEN** reindex is triggered for a COMPLETED document
- **THEN** it goes through the same ingestion task as a fresh upload, and existing structural data/vectors are cleanly replaced, not duplicated

### Requirement: Appendices are never indexed or searched
Appendix content MUST bypass chapter splitting and vector indexing entirely; it MUST only be reachable via a dedicated read endpoint.

#### Scenario: A user searches for text that only appears in an appendix
- **WHEN** a search query matches text that exists only inside a document's appendix
- **THEN** no result is returned from vector search for that text — it is only accessible via the appendix read endpoint
