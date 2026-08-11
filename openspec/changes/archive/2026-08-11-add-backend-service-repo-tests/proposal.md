## Why

`backend/tests/` has zero real tests — only fixtures (confirmed this session: a bare `pytest backend/tests` run collects 0 items). The service and repository layer that owns auth, chat/AI-conversation, messenger, and notes business logic has no coverage at all; real bugs have already reached production undetected in this area (e.g. `backend_critical_fixes_2026_08_03` — messenger chat_id and AI-chat IDOR bugs). `migrate-tests-to-testcontainers` (archived earlier this session) just made a real Postgres available to backend tests with zero manual setup, removing the last blocker to writing tests that actually touch the database instead of guessing at mocks.

## What Changes

- Add tests for every repository class's CRUD methods (`AuthRepository`, `ChatRepository`, `MessageRepository`, `MessengerRepository`, `NoteRepository`, `UserRepository`) against the real testcontainers-backed Postgres.
- Add tests for every service class's primary methods (`AuthService`, `AuthHandler`, `ChatService`, `ConversationService`, `LLMClient`, `MessageService`, `MessengerService`, `NoteService`, `UserService`, `UnitOfWork`, `WebSocketManager`), at whichever test level actually matches how each class is wired (see `design.md` — several of these take a raw `session_factory`, not an injected repository, which changes what "unit" means for them in practice).
- Fix the session-only bug found while building `migrate-tests-to-testcontainers`: `test_user`/`test_user_bob` fixtures collide with the hardcoded seed IDs (Alice/Bob/Carol = 1/2/3) because the Postgres identity sequence for `users.id` is never advanced past the manually-inserted seed rows. This blocks any test that creates a fresh user via those fixtures — a prerequisite, not optional cleanup.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — this adds test coverage for behavior already documented in the existing backend specs: `user-authentication`, `user-profile-directory`, `admin-user-management`, `ai-chat-messaging`, `messenger-direct-chat`, `messenger-websocket-realtime`, `notes`. No requirement changes.)

## Impact

- Affected code: new files under `backend/tests/` (unit tests for pure-logic classes, integration tests for DB-touching classes), plus a small fixture fix in `backend/tests/conftest.py` (sequence reset after seeding).
- No production code changes beyond the sequence-bug fix's migration/fixture touch-up.
- Explicitly out of scope (see `design.md` Non-Goals): E2E/route-level tests through FastAPI's TestClient (including the two confirmed bugs `TESTING.md` §8 ranks as highest priority) and `rag_service` tests — separate, future changes.
