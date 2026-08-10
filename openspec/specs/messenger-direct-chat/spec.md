## Purpose
REST side of person-to-person messenger: create/list/delete DM chats and paginated message history.

## Requirements

### Requirement: Participant-scoped message history
Reading message history MUST verify the requester is a participant of the chat before returning any messages.

#### Scenario: Non-participant requests history
- **WHEN** a user requests message history for a DM chat they are not part of
- **THEN** the request is rejected, no messages are returned

### Requirement: Deletion notifies remaining participants
Deleting a DM chat MUST broadcast a `chat_deleted` event over WebSocket to the other participant(s), excluding the actor who deleted it.

#### Scenario: User deletes a shared chat
- **WHEN** user A deletes a DM chat with user B
- **THEN** user B's active WebSocket connection receives a `chat_deleted` event; user A's own connection does not
