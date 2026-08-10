## Purpose
Splits parsed chapters into parent/child chunks suitable for embedding, filtering noise and duplicate content.

## Requirements

### Requirement: Minimum content filter
Text blocks shorter than 80 characters or fewer than 10 words MUST be filtered out before chunking, to avoid indexing noise fragments.

#### Scenario: A heading-only fragment with no real content
- **WHEN** a parsed block is 20 characters long
- **THEN** it is excluded from chunk generation

### Requirement: Numbered-subpoint-aware child splitting
Child chunking MUST first attempt to split on numbered subpoints (e.g. `5.2.1`) before falling back to generic recursive character splitting.

#### Scenario: A parent chunk contains numbered subpoints
- **WHEN** a parent chunk's text contains `\d+\.\d+`-style numbered subpoints
- **THEN** child chunks are split along those subpoint boundaries rather than purely by character count

### Requirement: Hash-based parent deduplication
Parent chunks MUST be deduplicated per document using a whitespace-normalized content hash, so identical repeated text isn't indexed twice.

#### Scenario: The same boilerplate paragraph appears twice in a document
- **WHEN** two parent chunks within the same document have identical text after whitespace normalization
- **THEN** only one of them is kept for indexing
