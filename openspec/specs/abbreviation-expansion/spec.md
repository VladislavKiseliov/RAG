## Purpose
Expands search queries containing known document abbreviations, in both directions, using morphological analysis without an LLM.

## Requirements

### Requirement: Direct expansion for CAPS tokens
A single-token uppercase acronym matching a known abbreviation MUST have its expansion appended inline to the query.

#### Scenario: Query contains a known acronym
- **WHEN** a query contains a CAPS token matching a known acronym in the dictionary
- **THEN** the query is expanded to include the acronym's full expansion alongside the original acronym

### Requirement: Reverse expansion via lemma matching
A word sequence matching a known expansion, in any grammatical case or number (via lemma normalization), MUST have the corresponding acronym appended.

#### Scenario: Query uses an inflected form of a known expansion phrase
- **WHEN** a query contains a grammatically inflected form of a phrase known to expand to an acronym
- **THEN** the acronym is appended to the query even though the surface form doesn't match the dictionary literally

### Requirement: Overlap resolution
When multiple replacement spans overlap, only the first (by sorted order) MUST be applied; later overlapping spans MUST be skipped.

#### Scenario: Two candidate matches overlap in the same query text
- **WHEN** two abbreviation matches would apply to overlapping spans of the query
- **THEN** only one of them is applied, chosen deterministically by sort order

### Requirement: Startup-loaded dictionary
The abbreviation dictionary MUST be loaded into memory once at process startup, not per-request.
Known limitation: abbreviations from documents ingested after startup are not available until the process restarts.

#### Scenario: A new document with new abbreviations is ingested after startup
- **WHEN** a document containing new abbreviations is ingested while the service is already running
- **THEN** those new abbreviations are not available for query expansion until the next process restart
