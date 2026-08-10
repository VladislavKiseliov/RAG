## Purpose
LangGraph planner-first orchestration that is the single entry point for all `/llm/answer` traffic, replacing the previously-removed ML router.

## Requirements

### Requirement: Plan-driven routing
The planning step MUST classify a query into a route (`smalltalk` or `domain_rag`) based on whether the generated plan contains any subtasks.

#### Scenario: A greeting with no retrievable content
- **WHEN** the plan for a query results in zero subtasks
- **THEN** the query is routed to `smalltalk`, skipping retrieval entirely

### Requirement: Plan-failure fallback
If the planning LLM call fails or returns unparseable JSON, the system MUST fall back to a default single-subtask plan (`search_docs(query)`) rather than returning an error.

#### Scenario: The planning LLM returns malformed JSON
- **WHEN** the plan_node's LLM response fails to parse as JSON
- **THEN** a default plan searching the raw query is used instead of failing the request

### Requirement: Read-only tool enforcement at execution time
Subtask execution MUST refuse to run any tool whose declared access is not `read`, even if the plan requested it — defense in depth against a plan proposing a write action.

#### Scenario: A plan subtask requests a write-access tool
- **WHEN** `execute_subtasks_node` processes a subtask calling a tool with `access: "write"`
- **THEN** that subtask is skipped, not executed

### Requirement: Cross-round result merging by parent id
Search results from multiple subtask rounds MUST be merged into a single retrieval set keyed by `parent_id`, with newer results taking precedence over older ones for the same parent.

#### Scenario: The same document parent is retrieved in two different rounds
- **WHEN** a reflect-triggered second retrieval round returns a parent already present from the first round
- **THEN** the merged retrieval data keeps the newer round's version of that parent
