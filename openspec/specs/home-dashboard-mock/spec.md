## Purpose
UI scaffold, no backend contract. Global search, quick links, notifications, reminders, and "my tasks" widgets on the Home screen — all backed by hardcoded arrays, no real search index or backend endpoints exist yet.

## Requirements

### Requirement: No real cross-entity search index
Global search MUST NOT be presented as searching real chats/documents/notes — it currently matches only against a hardcoded `SEARCH_INDEX` array.
Rationale: production would need either a unified search index or three parallel queries (chats/docs/notes); neither exists.

#### Scenario: A user searches for a term that exists in a real document but not in the mock index
- **WHEN** the user searches Home for that term
- **THEN** no result is found, even though the term exists in the real knowledge base

### Requirement: Task toggling is the only mutable state
Of all Home widgets, only `toggleTask` on the seeded task list MUST mutate local state; all other widgets are read-only mock data.

#### Scenario: A user checks off a seeded task on Home
- **WHEN** `toggleTask` is called
- **THEN** the task's completed state changes locally; no backend call is made and the change does not persist across reload
