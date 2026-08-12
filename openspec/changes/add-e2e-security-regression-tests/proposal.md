## Why

Two real security bugs (`backend_critical_fixes_2026_08_03`) — a messenger IDOR (`MessageService.resolve_chat` trusted an unverified `chat_guid`→`chat_id` resolution, and `add_user_to_chat_handler` accepted a client-supplied `chat_id` directly) and an AI-chat IDOR (`ConversationService` resolved chats via `get_chat_by_guid` with no participant check) — were both found and fixed the same day, but neither has a regression test. `TESTING.md §8` named this "the highest payoff" item and it's the only item from that list still open (unit coverage on `ConversationService` and repository-layer integration tests were both closed in `add-backend-service-repo-tests`, archived 2026-08-11). Investigation for this change found that `TESTING.md`'s own documented e2e pattern (`httpx.ASGITransport`) doesn't run FastAPI lifespan, and that `starlette.testclient.TestClient` (already available transitively, no new dependency) covers both the REST bug and the WebSocket bug with the same tool — no separate "fake-WebSocket harness" design is needed, reversing an assumption recorded in `add-backend-service-repo-tests`'s design.md.

## What Changes

- Add `backend/tests/test_e2e_chat_idor.py` — full-stack regression test for the AI-chat IDOR: a user requests messages/streaming on a chat they are not a participant of, via the real FastAPI app (`TestClient`, not `ASGITransport`) and real routes (`POST /api/chats/{chat_guid}/messages`, `POST /api/chats/{chat_guid}/messages/stream`), authenticated with a real JWT, asserting `ChatNotFoundError`'s HTTP mapping (404), not 200/500.
- Add `backend/tests/test_e2e_messenger_chat_id.py` — full-stack regression test for the messenger IDOR: over a real WebSocket connection (`TestClient.websocket_connect`), a user sends `add_user_to_chat` for a chat they don't belong to, asserting it's rejected (not silently cached/trusted).
- `app.dependency_overrides[get_container] = lambda: <test container>` to point the real app at the existing testcontainers-backed `engine`/`session_factory` from `backend/tests/conftest.py`, instead of building a second, separate DB-provisioning path.
- No production code changes — both bugs are already fixed; this only adds the regression coverage that was never written.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — this adds test coverage for behavior already fixed and already documented in `ai-chat-messaging`/`messenger-websocket-realtime` specs. No requirement changes. `skip_specs: true` set in `.openspec.yaml`.)

## Impact

- Affected code: 2 new test files under `backend/tests/`; no production code touched.
- Depends on: `backend/tests/conftest.py`'s existing testcontainers Postgres infra (`migrate-tests-to-testcontainers`, archived 2026-08-10) — reused, not duplicated.
- Out of scope: any other WebSocket message types beyond `add_user_to_chat`; any other route beyond the two AI-chat message endpoints; fixing `TESTING.md`'s own e2e example (noting the lifespan gap here is enough, not part of this change's deliverable).
