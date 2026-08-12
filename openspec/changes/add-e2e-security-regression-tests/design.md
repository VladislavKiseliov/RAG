## Context

See `proposal.md` for motivation. Facts shaping the approach:

- `get_container` (`backend/dependencies.py:19-20`) reads `conn.app.state.container`, set only inside `backend/main.py`'s `lifespan`. `httpx.ASGITransport` (`TESTING.md`'s own §6 example) doesn't run lifespan — every route depending on `ContainerDep`/`CurrentUserDep`/etc. would 500 under that pattern as written. `starlette.testclient.TestClient` does run lifespan (`with TestClient(app) as client:`), so it's the right tool, not `ASGITransport`.
- `BackendContainer` (`backend/infrastructure.py:10-16`) is a frozen dataclass: `engine`, `session_factory`, `auth_handler: AuthHandler`, `llm_client: LLMClient`, `socket_manager: WebSocketManager`. All five are needed to satisfy `app.dependency_overrides[get_container]`, even though a given test only exercises a subset.
- `backend/tests/conftest.py`'s `test_user`/`test_user_bob` fixtures store `password="test-password"` as **plaintext**, not a bcrypt hash — `/auth/login` would fail `AuthHandler.verify_password` against it. Getting a valid bearer token for these fixtures means calling `AuthHandler.create_access_token(str(user.guid))` directly, not exercising the login route. This is a deliberate, narrower scope than "real auth" might suggest — login itself already has no test either way, and isn't what either bug is about.
- B2 (AI-chat IDOR): `ConversationService.process_message`/`process_message_stream` call `ChatRepository.get_chat_by_guid_for_participant` **before** touching `llm_client` at all (`conversation_service.py:114,161,185`) — the IDOR check happens first. A real LLM call never happens on the rejection path, so `llm_client` in the test container can point at an unreachable URL; it only needs to construct, never actually get called.
- B1 (messenger IDOR): `websocket_endpoint` (`backend/api/websocket_router.py:26-111`) requires, in order: (1) the socket connects to `/websocket/ws/`, (2) the first frame must be `{"type": "auth", "token": "..."}` within 10s or the socket closes (code 1008), (3) subsequent frames are dispatched by `type` to registered handlers via `socket_manager.handlers`. `add_user_to_chat_handler` (`websocket_handlers.py:127-142`) already correctly calls `message_service.resolve_chat(chat_guid, chats, current_user.id)` and on `ChatNotFoundError` sends `{"status": "error", "message": "Chat <guid> does not exist"}` via `socket_manager.send_error` — this is the fixed behavior; the regression test asserts exactly this response for a non-participant chat_guid.

## Goals / Non-Goals

**Goals:**
- One REST-level test (`test_e2e_chat_idor.py`) proving a non-participant gets 404 on both AI-chat message endpoints, through the real app/routes/DB, not a service-level unit test.
- One WebSocket-level test (`test_e2e_messenger_chat_id.py`) proving `add_user_to_chat` for a chat the sender isn't in gets rejected with an error frame, through the real WS handshake/dispatch loop.
- Reuse `backend/tests/conftest.py`'s existing testcontainers Postgres — no second DB-provisioning path.

**Non-Goals:**
- Testing the `/auth/login` route itself, or any other WebSocket message type (`user_typing`, `chat_deleted`, etc.) — out of scope, this change targets exactly the two historical bugs.
- Fixing `TESTING.md`'s own `ASGITransport` example to run lifespan — noting the gap here is sufficient; that's documentation, not code, and not what this change delivers.
- Building any reusable "E2E test harness" abstraction — two test files, not a framework. If a third E2E test shows up later, extracting shared setup becomes worth it then, not preemptively.

## Decisions

**`TestClient`, not `ASGITransport`, for both tests — including the REST one.** Even though B2 doesn't need WebSocket support, using `TestClient` for both keeps one dependency-override/container-construction pattern shared between the two files instead of two different HTTP-client setups, and sidesteps `ASGITransport`'s lifespan gap entirely.

**Test container built by hand, not `build_backend_infrastructure()`.** `build_backend_infrastructure()` reads `settings.DATABASE_URL` (points at whatever real DB `.env` configures) and constructs its own engine — using it in tests would silently reconnect to a real database instead of the testcontainers one. Instead, construct `BackendContainer(engine=<dedicated engine>, session_factory=<dedicated session_factory>, auth_handler=AuthHandler(secret_key="test-secret-key-at-least-32-bytes", algorithm="HS256", expire_minutes=15, refresh_expire_days=7), llm_client=LLMClient(service_url="http://unreachable.invalid"), socket_manager=WebSocketManager())` directly in a fixture, override `get_container` to return it.

**`backend_container`'s engine is its own, not the shared `engine`/`session_factory` fixtures.** Corrected during implementation (see Risks/Trade-offs) — `create_async_engine(pg_container.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg"))` built fresh inside the fixture, same testcontainers Postgres instance (same connection string shape as the shared `engine` fixture), but a distinct `AsyncEngine` object never touched outside `TestClient`'s own loop. Disposed in the fixture's teardown.

**Tokens via `auth_handler.create_access_token(str(user.guid))`, not `/auth/login`.** Matches the Context finding above (fixture users have plaintext, not bcrypt, passwords) — this is the same token-shape `/auth/login` would issue (same `AuthHandler`, same `sub` claim), just skipping the password round-trip that these fixtures can't support without changing `conftest.py`'s seed data (out of scope — surgical, don't touch existing fixtures for this).

**One test each, not a parametrized matrix across both message endpoints × both bugs.** `test_e2e_chat_idor.py` covers both `POST /api/chats/{chat_guid}/messages` and the `/stream` variant (2 assertions, same file, since both routes share the exact same IDOR-guard code path — `_validate_stream_chat_exists` and `process_message` both call the same repository method). `test_e2e_messenger_chat_id.py` covers only `add_user_to_chat` (the one handler the historical bug was actually in) — not every WS handler, per Non-Goals.

## Risks / Trade-offs

- [`TestClient` runs the ASGI app in its own background thread/event loop. **Confirmed during implementation**: the shared session-scoped `engine`/`session_factory` fixtures in `conftest.py` (used by every other backend test) get their asyncpg connections loop-bound the first time any test awaits a query through them — reusing that same `engine` object from inside `TestClient`'s different loop fails with `RuntimeError: ... attached to a different loop`. The HTTP-only spike (task 1.1) didn't catch this because it never touched the DB.] → **Fixed**: `backend_container` builds its own dedicated `AsyncEngine`/`session_factory` from `pg_container.get_connection_url()` (same testcontainers Postgres, different engine object), function-scoped, and performs no query through it before `TestClient` takes over — so the first real connection checkout happens naturally inside `TestClient`'s own loop, not the outer pytest-asyncio one.
- [Hand-built `BackendContainer` in tests could drift from what `build_backend_infrastructure()` actually constructs in prod if that function changes shape later] → Accepted: `BackendContainer` is a small, stable dataclass; a shape change there would already break the override at construction time (loud failure, not silent drift).

## Migration Plan

Not applicable (test-only, no production code changes, no deploy/rollback distinction). Order of work:
1. Spike: confirm `TestClient` works correctly nested inside this project's existing async pytest-asyncio setup, using the simplest possible request (e.g. an unauthenticated 401 on a protected route) before building either real test.
2. Shared test-container fixture (`BackendContainer` built from testcontainers `engine`/`session_factory` + fresh `AuthHandler`/`LLMClient`/`WebSocketManager`), `app.dependency_overrides[get_container]`.
3. `test_e2e_chat_idor.py` (B2).
4. `test_e2e_messenger_chat_id.py` (B1).
5. Run full `backend/tests`, confirm no regressions and both new tests fail-if-reverted (sanity: temporarily re-introduce each bug locally, confirm the new test catches it, then confirm it passes again against the real fixed code — not committed, just a local check).
