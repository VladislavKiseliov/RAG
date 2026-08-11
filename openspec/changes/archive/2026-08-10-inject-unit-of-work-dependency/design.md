## Context

See `proposal.md` for motivation. Current pattern, confirmed by reading the actual code (`chat_service.py`):

```python
class ChatService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory

    async def create_chat(self, ...):
        async with UnitOfWork(self._sf) as uow:
            chat = await uow.chats.create_chat(...)
            await uow.commit()
```

`backend/dependencies.py` constructs each service per-request via FastAPI's `Depends(get_chat_service)`, passing `container.session_factory` (a session-maker, not a session — a fresh session must be created per unit of work, not shared across a request).

## Goals / Non-Goals

**Goals:**
- `UnitOfWork` becomes an injected dependency, swappable in tests for a fake/mock, satisfying `CLAUDE.md`'s DI principle for real this time.
- Zero behavior change: identical transaction boundaries (one `UnitOfWork` per method call, same commit points), identical error handling.

**Non-Goals:**
- Not changing transaction boundaries to "one `UnitOfWork` per request" — a materially different, riskier change (see Decisions, rejected alternative).
- Not touching `UserService`/`ConversationService` — they don't use `UnitOfWork`, this is a different-shaped problem (see `proposal.md` Impact).
- Not changing `UnitOfWork`'s own internals (`__aenter__`/`commit`/`rollback`/`__aexit__`) — only how services obtain an instance.

## Decisions

**Inject a UoW-producing factory (`Callable[[], UnitOfWork]`), not a single shared `UnitOfWork` instance.**

Each service method still opens its own `UnitOfWork` (own session, own transaction) exactly as today — only *how* it gets that instance changes:

```python
class ChatService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]):
        self._uow_factory = uow_factory

    async def create_chat(self, ...):
        async with self._uow_factory() as uow:
            chat = await uow.chats.create_chat(...)
            await uow.commit()
```

Production wiring (`dependencies.py`):
```python
def get_chat_service(container: BackendContainer = Depends(get_container)) -> ChatService:
    return ChatService(uow_factory=lambda: UnitOfWork(container.session_factory))
```

Tests inject a factory returning a fake/stub UoW (mocked `.chats`/`.messages`/etc. repositories) with no real DB involved.

**Rejected alternative: inject one `UnitOfWork` instance per service (constructed once per request), methods reuse `self._uow` directly instead of opening a new one each call.**
This would actually simplify the code (no factory indirection) and is a legitimate pattern elsewhere. Rejected here specifically because it changes transaction boundaries: today, if `ChatService.get_history()` and a hypothetical second call in the same request both run, each gets its own transaction/session; under "one UoW per request" they'd share one, so a failure in one call could affect the other's uncommitted state depending on ordering. That's not what any current caller expects, and verifying "does anything currently rely on per-call transaction isolation" across every route touching these five services is a bigger, separate audit than "make this testable." The factory approach gets the testability win with zero risk of this class of regression.

**`uow_factory` return type stays `UnitOfWork`, not an abstract protocol/interface.**
`CLAUDE.md` calls for interfaces behind infrastructure (`Protocol`) for swappable infra — but `UnitOfWork` here is already a thin, in-repo class (not a third-party client like S3/Qdrant), and tests can construct a real `UnitOfWork`-shaped fake (or genuinely subclass it) without needing a formal `Protocol`. Introducing one now would be added ceremony with no swappable-implementation need beyond tests.

## Risks / Trade-offs

- [Five constructor signature changes ripple to `dependencies.py` and nowhere else — confirmed by grepping for `ChatService(`/`MessageService(`/etc. outside `backend/services/`] → Low risk, single call site per service, all in one file.
- [`lambda: UnitOfWork(container.session_factory)` closures are easy to get subtly wrong (e.g. capturing container by reference vs value)] → Standard Python closure semantics apply cleanly here since `container` doesn't get reassigned; no loop-variable-capture footgun since each `get_*_service` function has its own `container` parameter.

## Migration Plan

1. Update `UnitOfWork` usage in the five services to take `uow_factory` via constructor, replacing every inline `UnitOfWork(self._sf)` call with `self._uow_factory()`.
2. Update `backend/dependencies.py`'s five `get_*_service` functions accordingly.
3. Run backend's test suite (currently just the `test_conftest_smoke.py` throwaway + whatever `add-backend-service-repo-tests` has landed by then) to confirm no behavior change.
4. Manually smoke-test one full round-trip per affected service through the running app (create a chat, send a messenger DM, create a note, log in) — this change touches every request path that uses these five services, so a purely-static review isn't enough confidence.

Rollback: revert the five service files + `dependencies.py` (git revert) — no data migration, no API shape change, safe to roll back at any point.
