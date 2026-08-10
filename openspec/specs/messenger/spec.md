## Purpose
Real-time 1:1 chat client over WebSocket, with auto-reconnect, typing indicators, and read receipts.

## Requirements

### Requirement: Token sent as first frame, not in URL
The WebSocket client MUST authenticate by sending the token as the first frame after the connection opens, not as a URL query parameter, to avoid leaking it into proxy access logs.

#### Scenario: The WebSocket connection opens
- **WHEN** `onopen` fires
- **THEN** the client's first sent frame is `{type:'auth', token}`, and the connection URL contains no token

### Requirement: Exponential-backoff auto-reconnect
On unintentional disconnect, the client MUST attempt to reconnect with exponential backoff from 1s up to a 30s cap.

#### Scenario: The WebSocket connection drops unexpectedly
- **WHEN** the connection closes without the client having intentionally closed it
- **THEN** reconnect attempts begin at 1s and back off up to a 30s ceiling, not retrying instantly in a tight loop

### Requirement: Auto-clearing typing indicator
A `user_typing` event MUST set a per-chat, per-user timeout after which the typing indicator clears automatically, in case a matching "stopped typing" event never arrives.

#### Scenario: A user starts typing then goes idle without sending
- **WHEN** a `user_typing` event is received and no further activity follows
- **THEN** the typing indicator clears itself after the timeout, not staying on indefinitely

### Requirement: Idempotent read receipts
A read receipt MUST be sent whenever the last message in an open chat changes, and MUST be safe to send redundantly.

#### Scenario: The same last message triggers a read-receipt check twice
- **WHEN** the read-receipt effect runs again without the last message actually changing
- **THEN** sending a duplicate read receipt does not cause any visible inconsistency
