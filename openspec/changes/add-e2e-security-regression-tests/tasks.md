## 1. Spike

- [x] 1.1 Verify `starlette.testclient.TestClient` works correctly nested inside this project's existing async pytest-asyncio setup (`loop_scope="module"`/`"session"` in `pytest.ini`/`conftest.py`) — simplest possible check: an unauthenticated request to a protected route returns 401 through `with TestClient(app) as client:`. If this reveals a real incompatibility, pause and report before proceeding — do not guess a workaround. **Confirmed working.** Along the way found+fixed unrelated env drift: local `backend/.venv` had stale `fastapi==0.110.3` (predates the 0.136 SSE upgrade), blocking `from backend.main import app` entirely (`ModuleNotFoundError: No module named 'fastapi.sse'`) — synced venv via `pip install -r backend/requirements.txt`; full existing 146-test suite still green after the upgrade.

## 2. Shared test infrastructure

- [x] 2.1 Add a fixture building `BackendContainer` plus a fresh `AuthHandler` (test secret), `LLMClient` (unreachable URL — never called on the rejection paths under test), and `WebSocketManager` — **corrected during implementation**: the engine/session_factory could NOT reuse the shared session-scoped `engine`/`session_factory` fixtures (loop-bound to the outer pytest-asyncio loop from other tests already using them; `TestClient` runs the app in its own thread/loop, causing `RuntimeError: attached to a different loop`). Builds its own dedicated `AsyncEngine` from `pg_container.get_connection_url()` instead, disposed in teardown.
- [x] 2.2 Add a fixture that overrides `app.dependency_overrides[get_container]` with the container from 2.1, scoped/torn down per test
- [x] 2.3 Add a small helper to mint a bearer token for a `Users` row via `auth_handler.create_access_token(str(user.guid))` (not `/auth/login` — see design.md)

## 3. B2 — AI-chat IDOR regression

- [x] 3.1 `backend/tests/test_e2e_chat_idor.py`: using `test_user`/`test_user_bob`/`test_direct_chat`-style fixtures (a chat `test_user` is NOT a participant of), authenticate as `test_user`, `POST /api/chats/{other_chat.guid}/messages` — assert 404, not 200/500
- [x] 3.2 Same file: `POST /api/chats/{other_chat.guid}/messages/stream` — assert 404 (via `_validate_stream_chat_exists`'s dependency-level rejection)

## 4. B1 — messenger IDOR regression

- [x] 4.1 `backend/tests/test_e2e_messenger_chat_id.py`: open a WebSocket via `TestClient.websocket_connect("/websocket/ws/")`, send `{"type": "auth", "token": <test_user's token>}` as the first frame, confirm the connection stays open (no immediate close) — confirmed by dispatching an unknown message type and getting the router's own "not found" error back, not a disconnect
- [x] 4.2 Same file: send `{"type": "add_user_to_chat", "chat_guid": <a chat test_user is NOT a participant of>}`, assert the response is `{"status": "error", "message": "Chat <guid> does not exist"}` (via `socket_manager.send_error`), not silent acceptance

## 5. Verification

- [x] 5.1 Run the full `backend/tests` suite, confirm no regressions and both new tests pass — 150 passed
- [x] 5.2 Local-only sanity check (not committed): temporarily revert each fix in isolation, confirm its corresponding new test fails; revert the temporary change, confirm it passes again — B2 (`ChatRepository.get_chat_by_guid_for_participant`→`get_chat_by_guid`, both call sites in `conversation_service.py`) each independently failed their test when reverted; B1 (`message_service.resolve_chat`'s `get_chat_id_for_participant`→`get_chat_id_by_guid`) caused the test to hang (no error response sent) when reverted. All reverts undone, `git diff` on both files clean, full suite green again (150 passed)
