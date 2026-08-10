## Purpose
Disconnect-aware cancellation for the non-streaming `/llm/answer` endpoint, to avoid wasted LLM generation when a client has already given up and retried.

## Requirements

### Requirement: Cancel in-flight generation on client disconnect
If the client disconnects before the non-streaming answer completes, the in-flight LLM generation task MUST be cancelled.

#### Scenario: A client times out and retries while the original request is still generating
- **WHEN** the original HTTP connection disconnects mid-generation
- **THEN** that generation task is cancelled rather than continuing to consume LLM capacity for a response nobody will receive

### Requirement: Scoped to the non-streaming endpoint only
This cancellation mechanism MUST only apply to `/llm/answer`; the streaming endpoint has its own native disconnect handling and MUST NOT use this mechanism.

#### Scenario: A client disconnects from the streaming endpoint
- **WHEN** a client disconnects from `/llm/answer/stream`
- **THEN** cancellation is handled by the streaming endpoint's own logic, not by this capability
