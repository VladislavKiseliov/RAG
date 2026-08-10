## Purpose
Document library browsing with a floating draggable source viewer and chapter reader. Upload/list/read hit the real backend; post-upload indexing-status progression is currently simulated on the client, not driven by real completion events.

## Requirements

### Requirement: Lazy per-document chapter loading
Chapters (table of contents) for a document MUST be fetched only when that document is opened, not bundled into the initial document list response.

#### Scenario: The document list is displayed
- **WHEN** a user views the knowledge base list
- **THEN** no chapter data has been fetched for any document yet

### Requirement: Table markers interleaved at their original position
When rendering chapter text, `[→ Таблица N]` markers MUST be replaced with real table cards positioned where the marker appeared, not appended at the end of the chapter.

#### Scenario: A chapter's text contains a table marker mid-paragraph
- **WHEN** the chapter's full text is rendered
- **THEN** the table appears inline at that position, not collected at the bottom

### Requirement: Upload status progression is simulated, not event-driven
After a real upload, the transition to an "indexed" visual state MUST NOT be presented to the user as confirmed completion — it is a fixed client-side delay, not a signal from actual indexing completion.

#### Scenario: A document finishes uploading
- **WHEN** the upload request succeeds
- **THEN** the UI shows "indexed" after a fixed delay regardless of whether backend indexing has actually finished — this is a known gap, not a guarantee

### Requirement: Draggable viewer constrained to its container
The floating source viewer MUST be draggable within its parent bounds and MUST NOT support resizing.

#### Scenario: A user drags the source viewer toward the edge of the screen
- **WHEN** the user drags the floating viewer
- **THEN** it stays within the bounds of its parent container
