## 1. Dependencies

- [x] 1.1 Add `testcontainers` to `backend/requirements.txt` (`alembic`/`psycopg2-binary` already present)

## 2. backend fixtures

- [x] 2.1 Rewrite `backend/tests/conftest.py`'s schema setup to a session-scoped `pg_container` fixture (`PostgresContainer("postgres:18")`) + autouse fixture running `alembic upgrade head` (`Config("alembic.ini", ini_section="users")`), without touching the existing seed fixtures (Alice/Bob/Carol, `test_user`, `test_direct_chat`, `chat_repository`/`message_repository` wrappers)
- [x] 2.2 Run backend's test suite, confirm no regressions vs. the pre-migration pass count (baseline was actually 0 collected tests — see session notes; added a throwaway smoke test to prove the fixture chain works end-to-end, 2/2 pass)

## 3. Cleanup

- [x] 3.1 Remove `TEST_DB_HOST`/`TEST_DB_PORT`/`TEST_DB_USER`/`TEST_DB_PASS`/`TEST_DB_NAME` from `.env.example`

## 4. CI

- [x] 4.1 Add `.github/workflows/tests.yml` (checkout, setup-python 3.12, `pip install -r backend/requirements.txt`, `pytest backend/tests`) — no `services:` block, no healthcheck step

## 5. Verification

- [x] 5.1 Run `pytest backend/tests` locally end-to-end, confirm total pass count matches pre-migration baseline (0 → 2, see 2.2 note)
- [x] 5.2 Confirm a completely fresh clone (no local `.env` test vars, Docker running) can run the suite with zero manual setup (verified: `backend/.env` absent, no `TEST_DB_*`/`DB_*`/`MODE` env vars set, suite still passes — conftest.py no longer touches `backend.settings` at all)
