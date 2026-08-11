## Why

`backend` tests currently run `Base.metadata.drop_all`/`create_all` against a persistent `test_myapp_db`. This doesn't guarantee the test schema matches what `alembic upgrade head` actually applies in production, and the persistent DB requires manual one-time setup with real risk of "forgot to create the DB" (already hit in practice, per `TESTING.md`). This blocks safely starting the backend test-coverage effort — writing tests against infrastructure that's about to be replaced means rewriting fixtures twice.

`rag_service` has the same underlying problem and is documented as in-scope for the same fix in `TESTING.md` §3, but is deliberately **out of scope for this change** — this change covers `backend` only, so the two services can be migrated as independent, reviewable pieces of work instead of one large cross-service change.

## What Changes

- Add `testcontainers` (and `alembic`, `psycopg2-binary` if not already present) to `backend`'s test dependencies.
- Replace `backend/tests/conftest.py`'s schema setup with a session-scoped `PostgresContainer` fixture + `alembic upgrade head` (real migrations, not `create_all`/`drop_all`), without touching its existing seed fixtures (Alice/Bob/Carol, `test_user`, `test_direct_chat`).
- Remove `TEST_DB_*` variables from `.env`/`.env.example` — no longer needed, host/port/creds come from the container at runtime.
- Add `.github/workflows/tests.yml` scoped to `backend/tests` — trivial now, no `services:` block or healthcheck needed since the container lifecycle lives inside the pytest fixture.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — this is test/CI infrastructure only, it does not change any externally observable backend behavior. No product capability's requirements change.)

## Impact

- Affected code: `backend/tests/conftest.py`, `backend/requirements.txt`, `.env`/`.env.example`, new `.github/workflows/tests.yml`.
- New dependency: `testcontainers` (Python package, requires Docker available at test-run time — already true both locally and in CI per the design).
- No production code changes, no API changes.
- `rag_service`'s equivalent migration is separate, follow-up work — not part of this change.
