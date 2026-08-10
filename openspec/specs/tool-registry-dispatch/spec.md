## Purpose
Framework-agnostic registry of agent tools with declared read/write access, mostly scaffolding for future capabilities.

## Requirements

### Requirement: Explicit access declaration per tool
Every registered tool MUST declare whether it is `read` or `write` access, since this is what the agent graph's execution step enforces.

#### Scenario: A new tool is registered
- **WHEN** a tool is added to the registry
- **THEN** it must declare an `access` value of either `"read"` or `"write"`, with no implicit default

### Requirement: Unimplemented tools fail loudly, not silently
Tools that are registered but not yet implemented (`create_task`, `create_note`, `update_note`, `calc_gas`, `run_audit`, `get_chapter`, `get_document_passport`, `search_notes`, `search_tasks`) MUST raise `NotImplementedError` if invoked, rather than silently returning empty/fake results.

#### Scenario: A plan calls an unimplemented tool
- **WHEN** the agent attempts to invoke one of the not-yet-implemented tools
- **THEN** a `NotImplementedError` is raised, making the gap visible rather than masked

### Requirement: Only prompt-reachable tools are functionally live
Only tools referenced in `plan_prompt` (`search_docs`, `get_appendix`) SHALL be reachable by live LLM-generated plans; other real tools (like `list_documents`) exist in the registry but remain effectively unreachable until the prompt references them.

#### Scenario: list_documents is registered but not mentioned in the planning prompt
- **WHEN** a user asks a question that could benefit from `list_documents`
- **THEN** the planner does not call it, since the prompt gives it no way to know the tool exists
