## Context

See `proposal.md` for motivation. Facts shaping the approach:

- Root `alembic.ini` already has an `[rag]` section (`script_location = migrations/rag`) alongside `[users]` (the one `migrate-tests-to-testcontainers` already wired up for `backend`) — no new Alembic config needed, same `Config(str(ALEMBIC_INI), ini_section="rag")` pattern applies directly.
- The first rag migration (`79e89f76e01d_first_migration_in_posgres_18.py`) does `CREATE SCHEMA IF NOT EXISTS rag_kernel` itself — no manual `CREATE SCHEMA` step needed before `alembic upgrade head`, only `DROP SCHEMA IF EXISTS rag_kernel CASCADE` to reset.
- `migrations/rag/env.py` sets `version_table="alembic_version_rag"` but no `version_table_schema` — this table lands in the connection's default schema (`public` for role `myuser`), **not** inside `rag_kernel`. This matters: see Decisions.
- 3 of the 4 DB-touching files (`test_integration_document_orchestrator.py`, `test_integration_upload_webhook_flow.py`, `test_db/test_integration_database_document_service.py`) already do `DROP SCHEMA rag_kernel CASCADE` + `CREATE SCHEMA` + `Base.metadata.create_all` in their own **module-scoped** `engine` fixture, each duplicated verbatim (no shared `conftest.py` exists in `rag_service/tests/` today). Each file gets a fully wiped, freshly-rebuilt schema before its own tests run — this is a real isolation guarantee the current suite relies on (row-count assertions, "list all" queries), not incidental.
- `test_db/test_document_repository.py` is the outlier: no schema setup of its own at all, plus the hardcoded wrong-DB-name bug from `proposal.md`.
- `rag_service/requirements.txt` has neither `testcontainers` nor `alembic` yet (separate venv from `backend`).
- Two of the four files also depend on a real, non-containerized MinIO instance (`S3StorageRepository` against `settings.minio_private_url`) — untouched by this change (Postgres only, see Non-Goals).

## Goals / Non-Goals

**Goals:**
- One shared `rag_service/tests/conftest.py` providing `pg_container` (testcontainers, session-scoped — reused across all 4 files, versus today's "no container, one hand-run local Postgres") and real Alembic-migrated schema provisioning, replacing `Base.metadata.create_all` everywhere it's used.
- Preserve each file's existing **module-level** schema-reset isolation (freshly wiped `rag_kernel` before that module's tests) — not collapse to backend's session-scoped-once-seeded pattern, because these files' assertions depend on a clean slate per module, not on a shared fixed dataset.
- `test_document_repository.py` gets the same shared fixtures as its siblings — eliminates the hardcoded connection string entirely (there is no longer a per-file connection string to mistype).
- Remove `TEST_DB_*`/`MODE`-branching from `rag_service/settings.py`, matching `backend/settings.py`.

**Non-Goals:**
- Containerizing MinIO/S3 — `test_integration_document_orchestrator.py` and `test_integration_upload_webhook_flow.py` keep depending on a real local MinIO instance and `settings.minio_private_url`. Out of scope, matches `migrate-tests-to-testcontainers`'s Postgres-only precedent.
- Rewriting each file's test-level fixtures/isolation strategy (seed data, `created_doc_ids` cleanup, `_TestBucketStorage` adapters) — only the DB provisioning layer (`engine`/`session_factory` + how the schema gets there) moves into `conftest.py`. Per-test logic inside each file is untouched.
- Wiring `rag_service/tests` into `.github/workflows/tests.yml` — needs a MinIO service container for 2 of the 4 files, a separate concern from this change.
- `tests/rag_core_test/ChunkingEngine.py` — not `test_*.py`-named, not pytest-collected, not part of the automated suite.

## Decisions

**Module-scoped schema reset, not session-scoped-once.** Alternative considered: mirror `backend/tests/conftest.py` exactly — migrate the schema once per session, seed fixed data, rely on per-test row cleanup (backend's `test_user`-style fixtures). Rejected: it would require redesigning cleanup logic inside all 4 files (bigger, more invasive change than "swap the DB provisioning layer"), and these files' own docstrings/design already commit to "disposable schema, rebuilt fresh" semantics that work today. Keeping module-scoped reset is the surgical option — `conftest.py` centralizes the *how* (real migrations instead of `create_all`), not the *when*.

**`conftest.py` must explicitly reset `alembic_version_rag`, not just `DROP SCHEMA rag_kernel CASCADE`.** Because the version-tracking table lives outside `rag_kernel` (see Context), a plain schema drop leaves Alembic believing it's already at `head` on the next module's reset — `command.upgrade(cfg, "head")` would then silently no-op, leaving `rag_kernel` missing entirely for that module's tests. The module-scoped reset fixture must also `DROP TABLE IF EXISTS alembic_version_rag` (verify actual schema — likely `public` — against the running container before finalizing tasks.md's implementation step) before calling `command.upgrade`. This is the one part of "swap `create_all` for real migrations" that isn't a drop-in replacement, and is exactly the kind of gotcha that would otherwise silently break test isolation between files.

**One `pg_container`, `_migrated_schema`/reset logic exposed as a plain fixture each file's `engine` depends on (not autouse).** Unlike `backend/tests/conftest.py` (where `_migrated_schema` is `autouse=True` because every test in the file needs the one shared schema), here the reset must run once per *module* and only for modules that use it — an autouse session-scoped fixture would defeat the per-module wipe. Each of the 4 files keeps a thin local `engine`/`session_factory` fixture pair depending on the shared reset fixture + `pg_container`, rather than one autouse global.

**Fix scope for `test_document_repository.py`:** delete its local `engine` fixture (and the `assert settings.MODE == "TEST"` line) entirely; it picks up the shared `engine`/`session_factory` fixtures from `conftest.py` like every other file. No behavior to preserve here beyond "connects to the right schema" — it never had its own reset logic to begin with.

**`rag_service/settings.py`:** remove `TEST_DB_HOST/PORT/USER/PASS/NAME` fields and the `MODE == "TEST"` branch in `DATABASE_URL`, leaving it always resolve to `DB_*` (verified `settings.MODE` isn't read anywhere else in `rag_service` app code). `MODE` field itself stays (same as `backend/settings.py` — other code/compose may still reference the env var), only the branching logic goes.

**Dependencies:** add `testcontainers==4.15.0` and `alembic==1.18.4` to `rag_service/requirements.txt`, matching the exact versions already pinned in `backend/requirements.txt`.

## Risks / Trade-offs

- [Container startup cost per `pytest rag_service/tests` run, on top of the existing per-module `DROP SCHEMA`/migrate cost] → Accepted: `pg_container` is session-scoped (one container, ~5s startup per backend's precedent), only the schema-level reset repeats per module — no worse than today's per-module `create_all`, and removes the manual "set up a local Postgres by hand" step entirely.
- [`alembic_version_rag` living in an unexpected schema if Postgres role defaults differ from assumption] → Mitigated by verifying against the actual running container as an explicit task before relying on it (see tasks.md) rather than assuming.
- [Losing the "fresh schema per module" safety net if a future test file forgets to depend on the reset fixture] → Same risk profile as today (each file already opts in explicitly); not made worse by this change.
- [Two files still depend on a real local MinIO — testcontainers migration doesn't make the full suite hermetic] → Explicit Non-Goal, not a silent gap; unchanged from current state.

## Migration Plan

Not applicable in the deploy sense (test-only, no production rollout). Order of work:
1. Add `testcontainers`/`alembic` to `rag_service/requirements.txt`.
2. Build `rag_service/tests/conftest.py`: `pg_container` (session-scoped) + module-scoped schema-reset fixture (drop `rag_kernel` CASCADE + drop `alembic_version_rag` + `alembic upgrade head` via `ini_section="rag"`) + `engine`/`session_factory` fixtures built on top.
3. Migrate the 3 files with existing `create_all`-based fixtures onto the shared ones (remove their duplicated engine setup, drop their now-redundant `MODE` assertions).
4. Fix `test_db/test_document_repository.py` onto the same shared fixtures (removes the hardcoded connection string).
5. Simplify `rag_service/settings.py` (`DATABASE_URL`, drop `TEST_DB_*`).
6. Run the full `rag_service` DB-touching test subset, confirm green (MinIO-dependent tests still need a local MinIO running, same precondition as today).
