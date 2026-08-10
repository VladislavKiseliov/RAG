## Purpose
UI scaffold, no backend contract. Full Projects workflow (list/overview/files/queue/archive/document views, changeset approve/reject) — entirely seeded and mutated client-side, no API calls anywhere in this hook.

## Requirements

### Requirement: Changeset conflict detection is a local comparison
A changeset MUST be flagged as conflicting when its `fromVersion` doesn't match the document's current `approvedVersion`, computed entirely from local seeded state.

#### Scenario: Two changesets are proposed against the same document version, one gets approved first
- **WHEN** the second changeset's `fromVersion` no longer matches the document's `approvedVersion` after the first approval
- **THEN** the UI flags the second changeset as conflicting

### Requirement: Demo role switcher is explicitly temporary
The `role: 'manager'|'engineer'` switcher MUST be understood as a development aid standing in for a real session-derived role, to be removed once a real role model exists for Projects.

#### Scenario: A future change wires Projects to a real backend
- **WHEN** real project data and a real user-role model are introduced
- **THEN** the manual role switcher is removed rather than kept alongside real role data
