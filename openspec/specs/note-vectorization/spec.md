## Purpose
Lighter-weight vectorization path for user notes (not documents) — no Docling/S3/Postgres structural involvement, backend owns the note text itself.

## Requirements

### Requirement: Separate collection from documents
Note vectors MUST be stored in a dedicated Qdrant collection, keyed by `note_id`/`user_id` payload fields, separate from the document collection.

#### Scenario: A note is indexed
- **WHEN** a note is vectorized
- **THEN** its vectors go into the notes-specific collection, not the document collection

### Requirement: Idempotent reindex
Reindexing a note MUST delete its old vector points (by `note_id`) before inserting new ones.

#### Scenario: A note is edited and reindexed
- **WHEN** a previously-indexed note is reindexed after an edit
- **THEN** the old vectors for that note are removed before the new ones are inserted

### Requirement: Completion callback to backend regardless of outcome
On completion, whether success or failure, a callback MUST be posted to backend's internal index-complete endpoint, since backend owns the note's status field.

#### Scenario: Note indexing fails
- **WHEN** vectorization of a note fails
- **THEN** a callback is still sent to backend reporting the failure, so the note's status doesn't remain stuck at "indexing"
