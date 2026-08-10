## Purpose
Converts raw PDF/DOCX bytes into cleaned markdown, structured chapters, tables, and meta sections using Docling.

## Requirements

### Requirement: Numbered-heading chapter splitting with fallback
Chapters MUST be split on numbered headings (e.g. `5.2 Title`); documents without any numeric headings MUST fall back to fixed-size pseudo-chapters rather than producing one giant chapter.

#### Scenario: Document has no numbered headings
- **WHEN** a converted document contains no numeric section headings
- **THEN** the pipeline splits it into fixed-size pseudo-chapters instead of failing or returning a single chapter

### Requirement: Orphan chapter merging
A heading with no body text ("orphan") MUST be merged into the previous chapter unless it has sub-chapters of its own.

#### Scenario: A bare heading precedes a sub-numbered section
- **WHEN** a heading has no body text but is immediately followed by numbered sub-headings
- **THEN** it is kept as its own chapter (not merged), since it has children

### Requirement: Table markers inserted in chapter text
Extracted tables MUST be replaced in chapter markdown with a resolvable marker (`[→ Таблица N]`), not inlined as raw markdown, so retrieval/read time can resolve them separately.

#### Scenario: A chapter contains a table
- **WHEN** a chapter's source contains a table
- **THEN** the chapter's stored markdown contains a `[→ Таблица N]` marker at the table's position, and the table content is stored separately
