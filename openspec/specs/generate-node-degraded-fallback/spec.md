## Purpose
Retry and fallback chain for LLM stream failures during answer generation, so a gateway hiccup doesn't fully fail the request.

## Requirements

### Requirement: Retry only before the first token
Streaming failures MUST only be retried (with exponential backoff) if they occur before any tokens have been streamed to the client; once generation has started, a failure MUST NOT trigger a retry (which would duplicate content).

#### Scenario: A transient error occurs after some tokens have already streamed
- **WHEN** the LLM stream fails midway after tokens have already been sent to the client
- **THEN** no retry happens — instead an interruption marker is appended and the response is flagged degraded

### Requirement: Non-streaming fallback on total stream failure
If a streaming attempt produces zero tokens across all retries, the system MUST fall back once to a non-streaming generation call before giving up.

#### Scenario: The streaming endpoint fails on every retry with zero tokens produced
- **WHEN** all streaming retry attempts fail before producing any token
- **THEN** a single non-streaming generation call is attempted as a last resort

### Requirement: Degraded responses are flagged, not silently returned
Any response that hit a stream failure or fallback path MUST be marked `degraded=True` and surfaced to callers via a `done.degraded` signal.

#### Scenario: A response was completed via the non-streaming fallback
- **WHEN** an answer is produced through the fallback path after a stream failure
- **THEN** the response is marked degraded so downstream consumers (e.g. backend) know not to persist it into conversation summary
