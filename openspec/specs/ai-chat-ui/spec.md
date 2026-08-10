## Purpose
SSE-streamed chat UI against the AI assistant, with per-conversation history and clickable source citations.

## Requirements

### Requirement: URL-persisted conversation identity
The active conversation id MUST live in the URL (`/chats/:conversationId`), so a page refresh or back-navigation does not lose the user's place.

#### Scenario: A user refreshes the page mid-conversation
- **WHEN** the user reloads the browser while a conversation is open
- **THEN** the same conversation is shown, not the default/empty state

### Requirement: SSE event-type dispatch
The client MUST parse SSE frames and dispatch behavior per `event:` type — `token` appends/creates the assistant bubble, `sources` attaches citations, `status` shows a progress label, `error` shows a fallback bubble, `ping` is a no-op.

#### Scenario: A `sources` event arrives after token events
- **WHEN** the stream sends a `sources` event following a sequence of `token` events
- **THEN** the citations are attached to the message the tokens built, not a new message

### Requirement: Auto-create conversation on first message
Sending a message with no conversation selected MUST create a new conversation first, then send the message into it.

#### Scenario: A user types a message with no chat open
- **WHEN** the user sends a message while no conversation is selected
- **THEN** a new conversation is created and the message is sent as its first message

### Requirement: Abortable history fetch on conversation switch
Switching conversations MUST abort any in-flight history fetch for the previously selected conversation.

#### Scenario: A user rapidly switches between two conversations
- **WHEN** the user opens conversation B before conversation A's history fetch has completed
- **THEN** conversation A's fetch is aborted and does not overwrite B's displayed history
