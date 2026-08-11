from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"


# ── Контейнер (session-scoped, один на весь прогон) ───────────────────────────

@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:18") as pg:
        yield pg


# ── Сброс схемы (module-scoped, не autouse) ────────────────────────────────────
# Каждый из 4 файлов, трогающих БД, явно запрашивает эту фикстуру через engine/
# session_factory ниже — получая свежую, полностью пересобранную по реальным
# Alembic-миграциям схему перед своими тестами, независимо от того, что оставил
# после себя любой другой файл. Не session-scoped/autouse (в отличие от
# backend/tests/conftest.py) — там один общий сид на весь прогон, здесь каждый
# файл полагается на чистый slate именно на уровне модуля.

@pytest.fixture(scope="module")
def rag_schema_reset(pg_container):
    sync_url = pg_container.get_connection_url()  # postgresql+psycopg2://...

    reset_engine = create_engine(sync_url)
    with reset_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS rag_kernel CASCADE"))
        # alembic_version_rag живёt в `public` (migrations/rag/env.py задаёт
        # version_table, но не version_table_schema) — DROP SCHEMA rag_kernel
        # его не тронет, и Alembic на следующем upgrade("head") решит, что всё
        # уже накачено, и молча ничего не сделает, оставив rag_kernel отсутствующей.
        conn.execute(text("DROP TABLE IF EXISTS public.alembic_version_rag"))
    reset_engine.dispose()

    cfg = Config(str(ALEMBIC_INI), ini_section="rag")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    # alembic.ini's [rag] section declares `script_location = migrations/rag` without
    # `%(here)s` — Alembic resolves that relative to the process CWD, not the ini file's
    # own directory. Pin it absolute so this fixture works regardless of where pytest is
    # invoked from (rag_service's own settings loading is itself CWD-sensitive - see
    # RagSettings.model_config's env_file tuple - so tests may legitimately run from
    # either the repo root or rag_service/).
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations" / "rag"))
    command.upgrade(cfg, "head")


# ── Engine + session_factory (module-scoped) ──────────────────────────────────

@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def engine(pg_container, rag_schema_reset):
    async_url = pg_container.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")
    engine = create_async_engine(async_url, future=True, echo=False)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
