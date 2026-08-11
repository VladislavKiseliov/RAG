## 1. Dependencies

- [x] 1.1 Add `testcontainers==4.15.0` and `alembic==1.18.4` to `rag_service/requirements.txt`, matching the versions pinned in `backend/requirements.txt`

## 2. Shared conftest.py

- [x] 2.1 Create `rag_service/tests/conftest.py` with a session-scoped `pg_container` fixture (`PostgresContainer("postgres:18")`), matching `backend/tests/conftest.py`'s pattern
- [x] 2.2 Verify against the running container which schema `alembic_version_rag` actually lands in (per `migrations/rag/env.py`'s `version_table="alembic_version_rag"` with no `version_table_schema` — expected `public`, confirm before hardcoding) — **confirmed: `public`**, via a throwaway PostgresContainer + `alembic upgrade head` run
- [x] 2.3 Add a module-scoped schema-reset fixture: `DROP SCHEMA IF EXISTS rag_kernel CASCADE`, `DROP TABLE IF EXISTS <verified-schema>.alembic_version_rag`, then `command.upgrade(Config(ALEMBIC_INI, ini_section="rag"), "head")` against `pg_container`'s connection URL
- [x] 2.4 Add `engine`/`session_factory` fixtures (module-scoped, `loop_scope="module"`) built on top of `pg_container` + the reset fixture, for the 4 test files to depend on

## 3. Migrate existing create_all-based files

- [x] 3.1 `test_integration_document_orchestrator.py` — remove its local `engine`/`session_factory` fixtures and `assert settings.MODE == "TEST"`; depend on the shared conftest fixtures instead (also fixed `created_doc_ids`, which built its own second ad-hoc engine via `settings.DATABASE_URL` for cleanup — now reuses `session_factory`)
- [x] 3.2 `test_integration_upload_webhook_flow.py` — same (its `created_doc_ids` already depended on `session_factory` correctly, no second fix needed)
- [x] 3.3 `test_db/test_integration_database_document_service.py` — same (also dropped the now-obsolete D11 docstring about `create_all` schema drift, no longer applicable now that migrations apply the schema)

## 4. Fix the hardcoded-connection-string bug

- [x] 4.1 `test_db/test_document_repository.py` — remove the hardcoded `postgresql+asyncpg://myuser:mypassword@localhost:5432/myapp_db` engine fixture and the `assert settings.MODE == "TEST"` line entirely; depend on the shared conftest `engine`/`session_factory` fixtures like the other 3 files

## 5. Settings cleanup

- [x] 5.1 Remove `TEST_DB_HOST`/`TEST_DB_PORT`/`TEST_DB_USER`/`TEST_DB_PASS`/`TEST_DB_NAME` fields from `rag_service/settings.py`
- [x] 5.2 Simplify `DATABASE_URL` property to always resolve from `DB_*` (drop the `MODE == "TEST"` branch); leave the `MODE` field itself in place

## 6. Verification

- [x] 6.1 Run `pytest rag_service/tests/test_db/test_document_repository.py rag_service/tests/test_db/test_integration_database_document_service.py` — confirm both pass against the container, and that the second module's schema reset actually rebuilds `rag_kernel` (not a silent no-op from stale `alembic_version_rag`) — **31/31 passed**, second module's reset confirmed working across the module boundary
- [x] 6.2 Run `pytest rag_service/tests/test_integration_document_orchestrator.py rag_service/tests/test_integration_upload_webhook_flow.py` with a local MinIO running (pre-existing precondition, unchanged by this change) — confirm both pass — **11/11 passed** (from CWD=`rag_service/`; see note below on an unrelated CWD-dependent env-loading issue found and worked around in `conftest.py`, not fixed at the settings level)
- [x] 6.3 Run the full `pytest rag_service/tests` and confirm no regressions against the previously-green 120/120 baseline (`rag_service_test_rewrite_2026_08_03`) — **149/149 passed** (29 more than the 08-03 baseline — other test files added since then, unrelated to this change)
