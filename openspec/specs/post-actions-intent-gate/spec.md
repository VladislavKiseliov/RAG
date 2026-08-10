## Purpose
UI scaffold, no backend contract yet. Code-gated action-proposal stub that currently always returns no action, since the underlying write tools (`create_task`, `create_note`, `update_note`) are unimplemented.

## Requirements

### Requirement: Action-intent detection independent of route
Whether to invoke the post-actions step MUST be decided by a regex over the raw user query for action-like verbs (save/create task/note), independent of the smalltalk/domain_rag route.
Rationale: a prior bug skipped action requests that didn't also trigger a search.

#### Scenario: A user asks to save something without triggering a document search
- **WHEN** a query contains an action-like verb but the plan produced zero search subtasks (smalltalk route)
- **THEN** the post-actions step is still invoked, not skipped because of the route

### Requirement: Currently a true no-op
The post-actions node MUST always return `proposed_action: None` today, since none of the write tools it would propose are implemented.

#### Scenario: A user's query matches the action-intent regex
- **WHEN** post-actions is invoked
- **THEN** it returns no proposed action, because `create_task`/`create_note`/`update_note` are stubs
