## Purpose
The SSE contract for `/llm/answer/stream`, giving clients a fixed event sequence to render incrementally.

## Requirements

### Requirement: Fixed event sequence
The stream MUST emit events in the order: zero or more `status`, then zero or more `token`, then one `sources`, then one `done`.

#### Scenario: A normal successful answer is streamed
- **WHEN** an answer completes successfully
- **THEN** the client receives status events, then token events, then a sources event, then a done event, in that order

### Requirement: Mid-stream errors become error events, not HTTP errors
Once the SSE stream has begun (headers already sent), any failure MUST be surfaced as an `error` SSE event, never as an `HTTPException`.

#### Scenario: An error occurs after streaming has started
- **WHEN** a failure happens after the first SSE event has been sent
- **THEN** the client receives an `error` event within the stream, not an HTTP-level error response

### Requirement: Node code stays streaming-mode agnostic
Graph nodes MUST push `status`/`token` events via a stream writer that is a safe no-op outside a streaming run, so the same node code serves both `/llm/answer` and `/llm/answer/stream`.

#### Scenario: The same graph runs in non-streaming mode
- **WHEN** `/llm/answer` (non-streaming) invokes the same graph nodes used by the streaming endpoint
- **THEN** the nodes' stream-writer calls are no-ops and do not error
