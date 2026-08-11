## Why

`CLAUDE.md` states the project's architecture principle directly: "Dependency Injection — зависимости передаются через конструктор, не создаются внутри." Five services violate this specifically for their unit-of-work: `AuthService`, `ChatService`, `MessageService`, `MessengerService`, `NoteService` all do `async with UnitOfWork(self._sf) as uow:` **inside** each method, constructing `UnitOfWork` fresh every call instead of receiving it (or a way to produce it) via the constructor. This was surfaced while scoping `add-backend-service-repo-tests`: because `UnitOfWork` isn't an injected seam, those five services can't be given a mocked/fake unit-of-work in a test without monkeypatching the class reference inside each service module — a fragile technique the project doesn't otherwise use. Fixing the DI gap turns these into classically unit-testable services (mock the injected UoW-producer, no real DB needed) instead of requiring integration-level tests for everything.

## What Changes

- Change `AuthService`, `ChatService`, `MessageService`, `MessengerService`, `NoteService`'s constructors to accept an injected UnitOfWork-producing dependency instead of a bare `session_factory`, and replace each method's inline `UnitOfWork(self._sf)` construction with a call through that injected dependency.
- Update `backend/dependencies.py`'s `get_*_service` functions (the FastAPI DI wiring) to build and pass that dependency instead of the raw `session_factory`.
- Keep transaction/commit semantics byte-for-byte identical: still one fresh `UnitOfWork` per method call, same commit/rollback points — this is a testability refactor, not a transaction-boundary change (see `design.md` for the rejected alternative that *would* change transaction boundaries, and why it's rejected here).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — pure internal refactor for testability; no externally observable backend behavior changes. Same endpoints, same responses, same transaction/commit points.)

## Impact

- Affected code: `backend/services/unit_of_work.py`, `backend/services/auth_service.py`, `backend/services/chat_service.py`, `backend/services/messenger/message_service.py`, `backend/services/messenger/messenger_service.py`, `backend/services/note_service.py`, `backend/dependencies.py`.
- Not touched: `UserService`, `ConversationService` — they don't use `UnitOfWork` at all today (raw `session_factory()` + a single repository per call). Worth a follow-up look since `ConversationService` in particular touches both `ChatRepository` and `MessageRepository` without transactional atomicity between them, but that's a separate, different-shaped problem from "the DI is inline" — not folded into this change.
- Directly unblocks `add-backend-service-repo-tests` (already proposed, not yet applied): once this lands, that change's design.md DI-seam table should be revisited — several services move from "integration-only" to "classically unit-testable."
