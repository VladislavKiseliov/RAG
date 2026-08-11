## Why

`rag_service`'s 4 DB-touching test files each reimplement their own `engine` fixture against a hand-provisioned local Postgres (`rag_service/.env`, gitignored, set up manually per machine — see D11 in `rag_service/ISSUES.md`). Three of them already do `DROP SCHEMA rag_kernel CASCADE` + `Base.metadata.create_all` per module to fight schema drift, and say so in their own docstrings — the same drift risk `migrate-tests-to-testcontainers` (backend, archived 2026-08-10) already fixed by applying real Alembic migrations instead of ORM metadata. The 4th file, `tests/test_db/test_document_repository.py`, doesn't even do that: it hardcodes `postgresql+asyncpg://myuser:mypassword@localhost:5432/myapp_db` — the **production** database name, with a password that matches `TEST_DB_PASS` (not `DB_PASS`), while its own docstring says "against real PostgreSQL **test** DB". It currently fails to authenticate only because the real `myuser` Postgres password was rotated away from `mypassword` during `external_audit_verified_and_infra_hardening_2026-08-07` — an accident of timing, not a safeguard. The exact scenario documented in `SETUP_NEW_DEVICE.md`/`start_local_full.bat` (fresh `docker-compose.full.yml` bring-up, which defaults `POSTGRES_PASSWORD` to `mypassword`) would reactivate it, and the test performs real `INSERT`/`UPDATE`/`DELETE` against `rag_kernel.documents` and related tables with only best-effort cleanup.

## What Changes

- Add `rag_service/tests/conftest.py` (doesn't exist today) with shared, session-scoped `pg_container` (testcontainers) + `_migrated_schema` (real Alembic migrations, `ini_section="rag"` from the existing root `alembic.ini`) + `engine`/`session_factory` fixtures — mirroring `backend/tests/conftest.py`'s pattern from `migrate-tests-to-testcontainers`.
- Migrate `test_integration_document_orchestrator.py`, `test_integration_upload_webhook_flow.py`, and `test_db/test_integration_database_document_service.py` off their duplicated per-file `DROP SCHEMA ... create_all` engine fixtures onto the shared conftest fixtures.
- Fix `test_db/test_document_repository.py`: remove the hardcoded `myapp_db` connection string entirely — it now gets `engine`/`session_factory` from the same shared conftest fixtures as every other DB-touching file, so there is no per-file connection string left to drift or mistype.
- Remove `TEST_DB_*` fields and the `MODE`-based branch in `rag_service/settings.py`'s `DATABASE_URL` property (verified: `settings.MODE` is read nowhere else in `rag_service`'s app code) — same simplification `migrate-tests-to-testcontainers` made in `backend/settings.py`.
- Drop the now-redundant `assert settings.MODE == "TEST"` guards from all 4 test files (testcontainers is self-contained; app `MODE` is no longer relevant to whether tests can run).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
(none — this is test infrastructure and a test-file bug fix; no application-observable behavior changes. `skip_specs: true` set in `.openspec.yaml`.)

## Impact

- Affected code: new `rag_service/tests/conftest.py`; edits to 4 existing test files (`test_integration_document_orchestrator.py`, `test_integration_upload_webhook_flow.py`, `test_db/test_integration_database_document_service.py`, `test_db/test_document_repository.py`); `rag_service/settings.py` (`TEST_DB_*` fields + `DATABASE_URL` property).
- No production code changes beyond the settings simplification.
- Out of scope (see `design.md` Non-Goals): the two files' real-MinIO dependency (S3 storage stays as-is, not containerized here — this change is Postgres only, matching `migrate-tests-to-testcontainers`'s DB-only scope); CI wiring (`.github/workflows/tests.yml` currently only runs `backend/tests` — extending it to `rag_service/tests` needs a MinIO service container too, a separate concern); `tests/rag_core_test/ChunkingEngine.py` (a manual script, not `test_*.py`-named, not collected by pytest, not part of the automated suite).
