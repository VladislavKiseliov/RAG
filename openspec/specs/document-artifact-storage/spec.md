## Purpose
Persists parsed artifacts (full markdown, chapters, table CSV/HTML, meta sections) into MinIO under the document's key prefix, and structural rows into Postgres.

## Requirements

### Requirement: Oversized field truncation instead of bulk-insert failure
Chapter titles/numbers exceeding DB column limits MUST be truncated with a warning log, rather than aborting the entire bulk insert of chapters for a document.

#### Scenario: A chapter title exceeds 512 characters
- **WHEN** a parsed chapter's title is longer than the column limit
- **THEN** the title is truncated and the chapter is still inserted, with a warning logged; other chapters in the same document are unaffected

### Requirement: Structural data reset before re-insert
Reindexing or retrying ingestion MUST wipe prior chapters/tables/parent-chunk rows for the document before inserting new ones.

#### Scenario: A document is reindexed
- **WHEN** ingestion re-runs for a document that already has chapters/tables stored
- **THEN** the old rows are deleted before the new structural data is inserted, leaving no stale duplicates

### Requirement: Abbreviations parsed from meta section
An ABBREVIATIONS meta section, when present, MUST be parsed into `(acronym, expansion)` pairs and stored for later query expansion.

#### Scenario: A document has an abbreviations section
- **WHEN** Docling extracts a meta section recognized as an abbreviations list
- **THEN** each acronym/expansion pair is stored as a row usable by abbreviation-expansion
