## Purpose
Read-mostly proxy over rag_service's document catalog for the user-facing "Knowledge Base" screen (distinct from the admin panel: not admin-gated).

## Requirements

### Requirement: Document list always reads live data
Listing documents MUST always fetch fresh data from rag_service; it MUST NOT be served from any in-memory stub state.

#### Scenario: Client lists documents
- **WHEN** a user requests the document list
- **THEN** the response reflects rag_service's current catalog, not any locally cached/stub list

### Requirement: Upload/status-update endpoints are stub-only
The `upload_document` and `update_document_status` endpoints are explicitly non-persistent stubs; they MUST NOT be treated as the real ingestion path.
Rationale: the real upload path is the presigned-URL pipeline shared with the admin panel — these stub endpoints write to an in-memory list that `list_documents` never reads, so any write here disappears on next list.

#### Scenario: Client uploads via the stub endpoint
- **WHEN** a document is uploaded through this capability's stub endpoint
- **THEN** it does not appear in a subsequent call to list documents

### Requirement: Lazy per-document chapter fetch
Chapter/table-of-contents detail MUST be fetched lazily per opened document, not eagerly for the whole library, to avoid N+1 load on the list view.

#### Scenario: User opens the knowledge base list without opening any document
- **WHEN** a user views the document list screen
- **THEN** no chapter-detail requests are made until a specific document is opened
