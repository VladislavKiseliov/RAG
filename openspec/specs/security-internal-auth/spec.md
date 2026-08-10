## Purpose
Cross-service authentication for the two privileged inbound/outbound calls rag_service makes: the MinIO webhook and the backend notification callback.

## Requirements

### Requirement: Constant-time webhook token comparison
The inbound MinIO webhook bearer token MUST be compared using a constant-time comparison, not a standard string equality check, to avoid timing side-channels.

#### Scenario: An attacker attempts to guess the webhook token
- **WHEN** the webhook token is validated
- **THEN** the comparison uses `hmac.compare_digest` rather than `==`

### Requirement: Fire-and-forget outbound callback
The outbound callback to backend's internal notes endpoint MUST NOT raise or block the calling task if it fails; failures are logged only.

#### Scenario: Backend is temporarily unreachable during a callback
- **WHEN** rag_service tries to notify backend of note-indexing completion and backend is down
- **THEN** the exception is caught and logged, and the calling Celery task completes without failing
