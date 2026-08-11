## Context

See `proposal.md` for motivation. Current state, in detail (from `TESTING.md` §3, decision locked 2026-08-07 — scoped there to both services, this change deliberately covers `backend` only):

- `backend` tests: fixtures run `Base.metadata.drop_all`/`create_all` against a persistent `test_myapp_db`.
- Schema is otherwise owned exclusively by Alembic migrations (`migrations/users/`, section `[users]` in the root `alembic.ini`) — the test fixtures duplicating schema creation via ORM metadata is the actual problem, not just "a real DB would be nicer."
- `backend/requirements.txt` already declares `alembic==1.18.4` and `psycopg2-binary==2.9.11` (the sync driver Alembic's `[users]`/`[rag]` sections use) — no new migration-related dependency needed beyond `testcontainers` itself.

## Goals / Non-Goals

**Goals:**
- Test schema created exclusively by running the real Alembic migrations, so a test run is a live check that migrations actually apply cleanly — not a parallel, potentially-diverging ORM-metadata schema.
- Zero manual setup: a fresh clone with Docker installed can run `pytest backend/tests` with no prep step.

**Non-Goals:**
- `rag_service`'s equivalent migration — separate, follow-up change. Not touched here.
- Not migrating `qdrant`/`minio` test doubles to testcontainers — out of scope, no correctness gap there (unlike Postgres schema drift).
- Not introducing parallel test-run support (pytest-xdist etc.) — testcontainers makes it *safe* by construction (fresh container per session), but wiring parallel CI is separate, unscoped work.
- Not touching seed-data fixtures (`backend/tests/conftest.py`'s Alice/Bob/Carol, `test_user`, `test_direct_chat`, `chat_repository`/`message_repository` wrappers) — those seed rows, not schema, and are orthogonal to this change.

## Decisions

**Testcontainers over a persistent shared test DB or a CI `services:` block.**
Alternatives considered (full comparison already in `TESTING.md` §3):
- *Persistent test DB*: rejected — needs one-time manual creation, real risk of "forgot to set it up" (already happened in practice), and shared state can leak between runs if a schema reset is missed.
- *CI `services:` block*: rejected — adds a healthcheck/migration step in YAML that has to be kept in sync with local dev separately; doesn't solve the local-dev "did you create the DB" problem at all, only CI's.
- *Testcontainers*: chosen — schema creation is code (`command.upgrade(cfg, "head")` inside the fixture), not a manual or YAML-level step; identical behavior locally and in CI; a fresh container per test session gives perfect isolation by construction.

**Session-scoped container + autouse migration fixture.**
`PostgresContainer("postgres:18")` (version pinned to match `docker-compose.full.yml`'s prod image) started once per pytest session, with an `autouse=True` fixture running `alembic upgrade head` against it (`Config("alembic.ini", ini_section="users")`) before any test runs.

**No static test credentials.**
Host/port/user/password come from `pg_container.get_connection_url()` at runtime. `TEST_DB_*` env vars are removed from `.env`/`.env.example` — nothing to keep in sync or leak.

## Risks / Trade-offs

- [Docker must be available wherever tests run] → Already true today: local dev already requires Docker Desktop running for `docker-compose.full.yml`; GitHub Actions' `ubuntu-latest` runners have Docker preinstalled. No new environment requirement introduced.
- [Container startup adds latency per test session] → ~3-6s per `pytest` invocation per `TESTING.md`'s own measurement, once per session not per test. Acceptable since tests run mainly on push, not in a tight local edit-test loop.
- [`rag_service` keeps its own schema-drift risk until its follow-up change lands] → Accepted trade-off of splitting the two services into independent changes; `rag_service`'s current `DROP SCHEMA CASCADE`/`create_all` fixtures are untouched and keep working exactly as before, just not fixed yet.

## Migration Plan

1. Confirm `testcontainers` is added to `backend/requirements.txt` (Alembic/psycopg2 already present).
2. Rewrite `backend/tests/conftest.py`'s schema setup to the container + migration fixture, preserving seed fixtures untouched.
3. Remove now-unused `TEST_DB_*` from `.env`/`.env.example`.
4. Add `.github/workflows/tests.yml` scoped to `backend/tests`.
5. Run `pytest backend/tests` to confirm parity with the pre-migration pass count before considering this done.

Rollback: revert the conftest changes (git revert) — no production code or data is touched by this change, so rollback carries no runtime risk.
