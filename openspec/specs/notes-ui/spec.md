## Purpose
Frontend CRUD UI for personal notes, with AI-assisted generation and an async indexing status flow (client counterpart to the backend `notes` capability).

## Requirements

### Requirement: Async indexing status requires a delayed re-fetch
Saving and indexing a note MUST re-fetch the note after a delay, since the indexing completion happens asynchronously via a Celery callback, not synchronously in the save response.

#### Scenario: A user saves and indexes a note
- **WHEN** `saveAndIndex()` completes its immediate PATCH/POST calls
- **THEN** the UI re-fetches the note a few seconds later to pick up the final indexed status, rather than trusting the immediate response as final

### Requirement: Client-side folder/tag vocabulary matches backend constraints
Folders and tags offered in the UI MUST match the vocabulary the backend/LLM note-generation endpoint constrains to, so generated notes render consistently.

#### Scenario: A note is generated via AI
- **WHEN** `generateNote()` returns a note with a tag or folder
- **THEN** it is one of the fixed set the UI already knows how to render, not an arbitrary free-text value
