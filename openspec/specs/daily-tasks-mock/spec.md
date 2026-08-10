## Purpose
UI scaffold, no backend contract. Day-column task board with week navigation and a fake "AI" free-text task parser — entirely client-state, since no backend domain for "task" exists yet.

## Requirements

### Requirement: Carry-over is computed, not persisted
Unfinished tasks carrying over to the next day MUST be computed at render time from client state; this MUST NOT be presented as a persisted server-side rollover.

#### Scenario: A task from yesterday is still incomplete
- **WHEN** the task board renders today's column
- **THEN** the incomplete task is shown as carried over, recomputed from local state, not fetched from any backend rollover logic

### Requirement: Fake AI parser simulates latency
The free-text task parser (`parseAiTask`) MUST simulate network latency (~850ms) even though it runs entirely client-side with simple regex matching, to keep the UX consistent with an eventual real backend call.

#### Scenario: A user types a free-text task like "напомни завтра"
- **WHEN** the text is submitted to `parseAiTask`
- **THEN** the parsed result (date/urgency) appears only after the simulated delay, not instantly
