## Purpose
1-on-1 AI assistant conversations with RAG-backed answers, streamed or non-streamed, with rolling background summarization.

## Requirements

### Requirement: Chat access scoped to participant, never bare guid
Any read or write on a chat MUST resolve the chat id via the requesting user's participation, not by trusting a bare chat guid from the client.

#### Scenario: User requests a chat they don't belong to
- **WHEN** a user calls a chat endpoint with the guid of a chat they are not a participant of
- **THEN** the request is rejected as not found, not served

### Requirement: Streaming validates chat existence before headers are sent
The SSE streaming endpoint MUST validate that the target chat exists and is accessible before the event-stream response begins, since headers cannot be changed once sent.
Rationale: `EventSourceResponse` commits to a 200 status once the stream starts, so any not-found check has to happen earlier via `Depends`.

#### Scenario: Streaming to a nonexistent chat
- **WHEN** a client opens `/messages/stream` for a chat guid that doesn't exist or isn't theirs
- **THEN** the server returns 404 before any SSE frame is sent

### Requirement: Streaming survives client disconnect
Answer generation for a streaming request MUST continue and persist to history even if the client disconnects mid-stream.

#### Scenario: Browser tab closed mid-answer
- **WHEN** a user closes the browser tab while the assistant is still generating an answer
- **THEN** the generation task keeps running server-side and the completed answer is saved to chat history

### Requirement: Degraded responses are shown but not persisted
If the LLM service fails or degrades an answer, the user MUST still see a response, but it MUST NOT be written into chat history or feed the conversation summary.

#### Scenario: LLM service is unavailable
- **WHEN** the LLM service call fails during answer generation
- **THEN** the user sees a degraded/error response, but no assistant message is added to persisted history

### Requirement: Serialized background summarization
Conversation summarization MUST be serialized per chat so concurrent messages cannot produce a last-write-wins race on the summary.

#### Scenario: Two messages arrive almost simultaneously
- **WHEN** two messages in the same chat trigger summarization near-simultaneously
- **THEN** the summary updates from the two triggers do not overwrite each other silently — they are serialized via a per-chat lock
