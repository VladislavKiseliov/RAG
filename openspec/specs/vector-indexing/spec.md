## Purpose
Produces dense (TEI/e5) and sparse (BM25/FastEmbed) vector representations for text, applying correct query/passage instruction prefixes.

## Requirements

### Requirement: Correct query/passage prefix per direction
Text being embedded for search MUST be prefixed with `"query: "`; text being embedded for indexing MUST be prefixed with `"passage: "`. Mixing these degrades retrieval quality silently, so the distinction is a hard requirement, not a style choice.

#### Scenario: Embedding a user's search query
- **WHEN** a search query is embedded for retrieval
- **THEN** it is prefixed with `"query: "`, not `"passage: "`

#### Scenario: Embedding a chunk for indexing
- **WHEN** a document chunk is embedded for storage in the vector index
- **THEN** it is prefixed with `"passage: "`, not `"query: "`

### Requirement: Concurrent dense and sparse generation
Dense and sparse vectors for the same text MUST be generated concurrently, not sequentially, to minimize embedding latency for hybrid search.

#### Scenario: Indexing a chunk that needs both vector types
- **WHEN** a chunk requires both a dense and a sparse vector
- **THEN** both embedding calls are issued concurrently rather than one after the other
