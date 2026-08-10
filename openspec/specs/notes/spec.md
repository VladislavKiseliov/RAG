## Purpose
Personal notes owned by backend, with AI-assisted generation and an async RAG-indexing lifecycle delegated to rag_service.

## Requirements

### Requirement: Owner-only access
Every note operation MUST be scoped to the requesting user; notes owned by other users are treated as not found, not forbidden.

#### Scenario: User requests another user's note
- **WHEN** a user requests a note id that belongs to a different user
- **THEN** the response is `NoteNotFoundError`, not a permission error revealing the note exists

### Requirement: Indexing status rollback on failure
Triggering indexing MUST set status to `indexing`, and MUST roll back to `error` if the call to rag_service fails.

#### Scenario: rag_service indexing call fails
- **WHEN** `trigger_index` calls rag_service and the call fails
- **THEN** the note's status is set to `error`, not left stuck at `indexing`

### Requirement: Internal index-complete callback uses shared-secret auth
The `index_complete` webhook MUST authenticate via a shared-secret bearer token compared in constant time, not via a user session, since it is called by rag_service, not a browser.

#### Scenario: rag_service reports indexing completion
- **WHEN** rag_service calls the internal `index_complete` endpoint with a valid shared-secret bearer token
- **THEN** the note's status is updated to `indexed` without requiring a user JWT

### Requirement: Best-effort vector cleanup on delete
Deleting a note MUST attempt to delete its vectors in rag_service, but MUST NOT block or fail the note deletion if that network call fails.

#### Scenario: rag_service is unreachable during note deletion
- **WHEN** a user deletes a note and the rag_service vector-delete call fails
- **THEN** the note is still deleted from backend's database
