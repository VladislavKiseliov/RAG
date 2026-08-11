## Context

See `proposal.md` for motivation. Facts shaping the approach, most recent first:

- `inject-unit-of-work-dependency` (archived 2026-08-10) changed `AuthService`, `ChatService`, `MessageService`, `MessengerService`, `NoteService` to accept an injected `uow_factory: Callable[[], UnitOfWork]` instead of building `UnitOfWork(self._sf)` inline. This is a real, mockable constructor seam now — **the DI-seam table below has been revised from this design's original version to reflect it.** `UserService` and `ConversationService` were explicitly not touched by that change — they still take a raw `session_factory` and build a single repository directly per call.
- `backend/tests/` currently has zero test files (only `conftest.py`), confirmed by running the suite.
- `migrate-tests-to-testcontainers` (archived) rebuilt `backend/tests/conftest.py` around a real, session-scoped Postgres container with Alembic-applied schema — so integration-style tests (real DB, no mocking of SQLAlchemy) are cheap and correctness-guaranteeing where they're still the right level (repositories, `UnitOfWork` itself, and the two services still on raw `session_factory`).

## Goals / Non-Goals

**Goals:**
- CRUD coverage for every repository class against the real testcontainers Postgres (integration-level, matching `TESTING.md` §5's guidance: exercise real constraints/transactions/serialization, not something a mock can catch).
- Coverage for every service class's primary methods, at the test level each class's actual constructor seam supports (see Context) — not a blanket "mock everything" pass that would just test mocks.
- Fix the `test_user`/`test_user_bob` sequence-collision bug as a prerequisite — every fixture-created-user test depends on it.

**Non-Goals:**
- E2E/route-level tests through FastAPI's `TestClient` — including the two bugs `TESTING.md` §8 ranks as highest priority (messenger `chat_id`, AI-chat IDOR). Real, but a different test level and a separate change; not part of "CRUD operations on the service classes" as scoped here.
- `rag_service` — separate service, separate testcontainers migration not yet done (see `migrate-tests-to-testcontainers` proposal's explicit scope note).
- `websocket_handlers.py`/`websocket_utils.py` (module-level functions, not the `WebSocketManager` class) — these orchestrate live `WebSocket` protocol frames; covering them needs a fake-`WebSocket` test double that's a bigger, separate design decision (message-loop shape, not CRUD/service-method shape). `WebSocketManager` itself (the connection registry class) is in scope — it doesn't touch the live protocol, just tracks connections.
- Achieving a specific coverage percentage — this is "every class has tests for its primary paths," not a coverage-threshold target.

## Decisions

**Test level assigned per class, by actual DI seam (not by folder) — revised after `inject-unit-of-work-dependency`:**

| Class | Level | Why |
|---|---|---|
| `AuthRepository`, `ChatRepository`, `MessageRepository`, `MessengerRepository`, `NoteRepository`, `UserRepository` | Integration | Pure DB-CRUD classes, no seam to mock below the DB |
| `ChatService`, `MessageService`, `MessengerService` | Unit — mock `uow_factory` | Constructor now takes `uow_factory: Callable[[], UnitOfWork]`; inject a factory returning a fake `UnitOfWork` whose `.chats`/`.messages`/`.messenger` properties are `AsyncMock`s. No DB needed — asserts the service called the right repo method with the right args, not what the query returns |
| `AuthService` | Unit — mock `uow_factory` + `auth_handler` | Same factory seam, plus `auth_handler` was already mockable |
| `NoteService` | Unit — mock `uow_factory` + `llm_client` | Same factory seam, plus `llm_client` was already mockable |
| `UnitOfWork` | Integration | The class *implementing* the mockable seam above — testing it against a mock would be circular. Needs a real session to verify commit/rollback actually persists/discards across `.chats`/`.messages`/`.auth`/`.messenger`/`.notes` |
| `UserService` | Integration + mocked `auth_handler` | Not touched by `inject-unit-of-work-dependency` — still raw `session_factory()`, no injected UoW seam |
| `ConversationService` | Integration + mocked `llm_client` | Same — still raw `session_factory()`, not touched |
| `AuthHandler` | Unit | Pure logic — JWT encode/decode, password hash/verify, no I/O |
| `LLMClient` | Unit | HTTP client wrapping `httpx` calls to llm_service — mock the HTTP layer, not the DB |
| `WebSocketManager` | Unit | In-memory connection registry, no DB; mock the `WebSocket` objects it holds |

**Sequence-bug fix:** advance the Postgres identity sequences for `Users`/`Chats`/`Messages` (`pg_get_serial_sequence(...)` + `setval(...)` to `MAX(id)`) once, immediately after the seed inserts in the `engine` fixture in `backend/tests/conftest.py`. Portable across whatever the actual sequence names are (doesn't hardcode e.g. `users_id_seq`).

**One test file per class**, mirroring `backend/services/`'s and `backend/repository/`'s structure under `backend/tests/` (e.g. `backend/services/auth_service.py` → `backend/tests/test_auth_service.py`), not one giant file — matches how `rag_service/tests/` is already organized.

## Risks / Trade-offs

- [Remaining integration-heavy tests (repositories, `UnitOfWork`, `UserService`, `ConversationService`) are slower than a mocked unit suite] → Accepted, and now a smaller slice than originally scoped: five services moved to real unit tests once `uow_factory` became injectable. One shared session-scoped container keeps the remaining integration cost to "once per `pytest` session," not per test.
- [Mocking `auth_handler`/`llm_client` still leaves those two classes' own logic untested by the services that use them] → Mitigated: `AuthHandler` and `LLMClient` get their own direct unit tests (see table above), so their logic is covered once, not skipped.
- [Unit tests for `ChatService`/`MessageService`/`MessengerService`/`AuthService`/`NoteService` assert "called the right repo method," not "the query actually works"] → Accepted trade-off of unit-level testing generally; the repository-layer integration tests (group 2) cover "does the query actually work" for the same repo methods these services call, so the correctness gap is closed at that layer instead.
- [`websocket_handlers.py`/`websocket_utils.py` staying uncovered] → Explicit Non-Goal, not a silent gap — flagged for a future, separately-scoped change once a fake-`WebSocket` test harness is designed.

## Migration Plan

Not applicable in the usual sense (no production rollout) — this is additive test coverage. Order of work:
1. Fix the sequence bug in `conftest.py` (prerequisite — blocks fixture-created-user tests and the still-integration `UnitOfWork`/`UserService`/`ConversationService` tests).
2. Repository integration tests.
3. `UnitOfWork` integration test (reuses group 2's fixtures).
4. Unit tests for the five `uow_factory`-injected services (no DB needed — fastest group, can run in any order relative to 2/3).
5. Integration tests for `UserService`/`ConversationService` (mocked `auth_handler`/`llm_client`, real DB).
6. The three standalone-unit classes (`AuthHandler`, `LLMClient`, `WebSocketManager`).
