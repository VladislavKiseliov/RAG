## Purpose
Manages the Qdrant collection lifecycle and hybrid dense+sparse search/delete operations.

## Requirements

### Requirement: On-disk sparse vector index
The sparse (BM25) vector index MUST be configured with `on_disk=True`, to avoid loading the full sparse index into RAM and causing OOM on large collections.

#### Scenario: Collection is created for a large corpus
- **WHEN** the Qdrant collection is first created
- **THEN** the sparse vector index parameters have `on_disk=True` set

### Requirement: Hybrid fusion search
Search MUST fuse dense and sparse vector results server-side via DBSF fusion, prefetching each vector type at roughly double the requested top_k.

#### Scenario: A hybrid search request is issued
- **WHEN** a search is performed with both dense and sparse vectors available
- **THEN** results are a DBSF fusion of both, not just the dense-only ranking

### Requirement: Generic field-based deletion is a safe no-op on missing collection
Deleting points by a field (`doc_id` or `note_id`) MUST work for either field and MUST NOT raise if the collection doesn't exist yet.

#### Scenario: Deleting vectors for a document before any indexing has happened
- **WHEN** `delete_by_field("doc_id", ...)` is called and the Qdrant collection hasn't been created yet
- **THEN** the call completes without error
