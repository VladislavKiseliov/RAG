## Purpose
Live WebSocket channel for the messenger: authenticated handshake, message send, read receipts, typing indicators, and chat-removal events.

## Requirements

### Requirement: Auth via first frame, not query param
The client MUST authenticate by sending a JSON auth frame as the first message after connecting, not by passing a token in the WebSocket URL, to avoid tokens leaking into proxy/access logs.

#### Scenario: Client connects without sending an auth frame
- **WHEN** a client opens the WebSocket connection and does not send `{"type":"auth","token":...}` within 10 seconds
- **THEN** the server closes the connection with code 1008

### Requirement: Per-connection rate limiting without disconnect
Message sends over an authenticated connection MUST be rate-limited (10 messages / 10 seconds); exceeding the limit returns an error frame but keeps the connection open.

#### Scenario: Client sends messages faster than the limit
- **WHEN** an authenticated client sends more than 10 messages within a 10-second window
- **THEN** excess sends receive an error frame, and the connection is not closed

### Requirement: Message send resolves chat via participant scope
Sending a message over WebSocket MUST resolve the target chat id via the sender's participation, never trust a bare chat guid from the client, to prevent writing into a chat the sender doesn't belong to.

#### Scenario: Client sends a message with a guid for someone else's chat
- **WHEN** an authenticated client sends a message frame targeting a chat guid they are not a participant of
- **THEN** the message is rejected, not persisted or broadcast

### Requirement: Graceful handling of malformed frames
An unknown message type or malformed JSON MUST degrade gracefully with an error frame; it MUST NOT terminate the connection.

#### Scenario: Client sends invalid JSON
- **WHEN** the server receives a frame that isn't valid JSON or has an unrecognized `type`
- **THEN** an error frame is sent back and the connection loop continues
