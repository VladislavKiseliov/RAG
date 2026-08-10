## Purpose
UI scaffold, no backend contract. A fully fake, hardcoded "Projects" listing endpoint with no persistence or business logic, kept only to unblock frontend development.

## Requirements

### Requirement: Authenticated but not otherwise gated
The endpoint MUST require authentication but has no other authorization rules, since it returns no real per-user or per-project data.

#### Scenario: Any authenticated user requests projects
- **WHEN** any authenticated user calls `GET /api/projects`
- **THEN** the same hardcoded project list is returned regardless of who the user is

### Requirement: No persistence
This capability MUST NOT be relied upon for durable project data; nothing written here (there is no write endpoint) is ever backed by a database.

#### Scenario: A future proposal considers extending this endpoint
- **WHEN** real project persistence is proposed
- **THEN** it MUST be treated as a new capability (e.g. `projects`), not an extension of this stub
