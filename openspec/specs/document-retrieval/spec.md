## Purpose
The read-side RAG query path: turns natural-language queries into ranked parent-chunk results with resolved table content.

## Requirements

### Requirement: Batched multi-query search
Multiple queries in a single retrieval request MUST be served by one embedding call and one Qdrant batch request, not N sequential searches.

#### Scenario: A request contains several sub-queries
- **WHEN** `batch_search` is called with multiple queries
- **THEN** a single embedding call and a single Qdrant multi-request handle all of them

### Requirement: Parent-level dedup across batched queries
Child hits MUST be grouped by their parent chunk and deduplicated, keeping the best score when the same parent is matched by multiple queries.

#### Scenario: Two sub-queries both match children of the same parent chunk
- **WHEN** a batch search returns hits from two different queries pointing to the same parent
- **THEN** the parent appears once in the result set, with the best of the two scores

### Requirement: Table markers resolved at retrieval time
`[→ Таблица N]` markers present in retrieved parent text MUST be resolved into actual table markdown, batched per document to avoid N+1 fetches.

#### Scenario: A retrieved parent chunk contains a table marker
- **WHEN** retrieval returns a parent whose text contains `[→ Таблица N]`
- **THEN** the marker is replaced with the actual table content before being returned to the caller

### Requirement: Abbreviation expansion runs off the event loop
Query abbreviation expansion (CPU-bound lemmatization) MUST run via `asyncio.to_thread` so it does not block the event loop during retrieval.

#### Scenario: A retrieval request triggers abbreviation expansion
- **WHEN** a query is expanded for abbreviations before search
- **THEN** the expansion runs in a worker thread, not inline on the event loop
