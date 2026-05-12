"""pytest-xdist worker schema isolation utilities.

Each xdist worker (or master under -n0) gets a dedicated PostgreSQL
schema named ``test_<worker_id>`` (e.g. ``test_gw0``, ``test_master``).
The worker's SQLAlchemy engine sets ``search_path = "<schema>, public"``
so all ORM/raw SQL automatically resolves to the worker schema.

Production code (``database.py``, ``models/``, ``api/``, ``db/``,
``services/``) is byte-identical untouched; isolation only triggers when
``PYTEST_XDIST_WORKER`` is set or when this module is imported from
test conftest.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote_plus

import psycopg2
from psycopg2 import errors as pg_errors
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from db_config import POSTGRES_CONFIG

logger = logging.getLogger(__name__)


def worker_schema_name() -> str:
    """Return the PostgreSQL schema name for the current xdist worker.

    Reads env var ``PYTEST_XDIST_WORKER`` (set by pytest-xdist on each
    worker, e.g. ``gw0``/``gw1``). When absent (single-worker / master),
    returns ``test_master``.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    return f"test_{worker}"


def _build_dsn(*, async_driver: bool) -> str:
    cfg = POSTGRES_CONFIG
    pw = quote_plus(cfg["password"])
    driver = "postgresql+asyncpg" if async_driver else "postgresql+psycopg2"
    return (
        f"{driver}://{cfg['user']}:{pw}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
    )


def make_worker_engine(schema: str) -> AsyncEngine:
    """Build an async engine pinned to ``<schema>, public`` search_path.

    Uses NullPool because tests exercise the same monkeypatched engine
    from multiple asyncio event loops (pytest-asyncio per-test loops,
    FastAPI TestClient/anyio sync wrappers). asyncpg connections are
    loop-bound, so pooled reuse across loops triggers the
    ``Future ... attached to a different loop`` RuntimeError. NullPool
    opens a fresh connection per checkout, eliminating cross-loop reuse.
    See Oracle decision D12 in fix-pytest-xdist-isolation/design.md.
    """
    return create_async_engine(
        _build_dsn(async_driver=True),
        poolclass=NullPool,
        echo=False,
        connect_args={
            "server_settings": {
                "search_path": f"{schema},public",
                "statement_timeout": "30000",
            },
        },
    )


def make_worker_sessionmaker(engine: AsyncEngine) -> async_sessionmaker:
    """Return an async_sessionmaker bound to the given worker engine."""
    from sqlalchemy.ext.asyncio import AsyncSession

    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def _sync_psycopg2_connect(*, autocommit: bool = True):
    cfg = POSTGRES_CONFIG
    conn = psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
    )
    conn.autocommit = autocommit
    return conn


def create_worker_schema(schema_name: str) -> None:
    """``CREATE SCHEMA IF NOT EXISTS <schema>``.

    On insufficient privilege, raise ``PermissionError`` with the exact
    GRANT command needed to fix it (ops-friendly error path per design
    decision).
    """
    cfg = POSTGRES_CONFIG
    user = cfg["user"]
    db = cfg["database"]
    try:
        conn = _sync_psycopg2_connect(autocommit=True)
        try:
            with conn.cursor() as cur:
                cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
        finally:
            conn.close()
    except pg_errors.InsufficientPrivilege as exc:
        raise PermissionError(
            f"PostgreSQL user '{user}' lacks CREATE privilege on database "
            f"'{db}'. Fix with: "
            f"GRANT CREATE ON DATABASE {db} TO {user}; "
            f"(original: {exc})"
        ) from exc


def _build_sync_engine_for_schema(schema_name: str) -> Engine:
    return create_engine(
        _build_dsn(async_driver=False),
        connect_args={"options": f"-csearch_path={schema_name},public"},
        poolclass=None,
    )


def create_all_in_schema(schema_name: str) -> None:
    """Create every ORM table inside ``schema_name``.

    Uses sync SQLAlchemy + ``Base.metadata.create_all`` instead of
    alembic (alembic history contains ``op.execute`` against existing
    public data and would not replay against an empty schema; see
    design Decision 3).
    """
    # Local import: avoid pulling models at module import time so that
    # `tests/_db_isolation.py` can be imported by smoke scripts without
    # a database connection.
    from models import Base

    sync_engine = _build_sync_engine_for_schema(schema_name)
    try:
        with sync_engine.begin() as conn:
            conn.execute(text(f'SET search_path TO "{schema_name}"'))
            Base.metadata.create_all(bind=conn, checkfirst=False)
    finally:
        sync_engine.dispose()


def seed_default_plans(schema_name: str) -> None:
    """Insert the four production-equivalent rows into ``plans``.

    Mirrors production ``plans`` table (free / efficiency / professional
    / enterprise) so per-worker schemas can serve subscription-related
    tests without each test re-seeding. Idempotent: ``ON CONFLICT
    (plan_code) DO NOTHING``. Sync psycopg2 to fit the existing
    sessionstart sync setup path.
    """
    rows = [
        ("free", "免费版", "适合初次体验的用户",
         "基础物流模板|每日10次计算|基础功能", 10, 1, 0),
        ("efficiency", "效率版", "适合中小规模卖家",
         "极速模式|3个物流模板|无限次计算|优先客服", -1, 3, 1),
        ("professional", "专业版", "适合大规模专业卖家",
         "极速模式|10个物流模板|无限次计算|专属客服|数据导出", -1, -1, 2),
        ("enterprise", "企业版", "适合企业团队使用",
         "极速模式|无限物流模板|无限次计算|API接口|定制开发|7x24服务",
         -1, -1, 3),
    ]
    sync_engine = _build_sync_engine_for_schema(schema_name)
    try:
        with sync_engine.begin() as conn:
            conn.execute(text(f'SET search_path TO "{schema_name}"'))
            for code, name, desc, feats, calc_limit, log_limit, sort_order in rows:
                conn.execute(
                    text(
                        "INSERT INTO plans (plan_code, plan_name, description, "
                        "features, "
                        "display_price_month, display_price_year, "
                        "actual_price_month, actual_price_year, "
                        "test_price_month, test_price_year, "
                        "calc_limit, logistics_limit, is_active, sort_order) "
                        "VALUES (:code, :name, :desc, :feats, "
                        "0, 0, 0, 0, 0, 0, "
                        ":calc, :log, 1, :sort) "
                        "ON CONFLICT (plan_code) DO NOTHING"
                    ),
                    {
                        "code": code,
                        "name": name,
                        "desc": desc,
                        "feats": feats,
                        "calc": calc_limit,
                        "log": log_limit,
                        "sort": sort_order,
                    },
                )
    finally:
        sync_engine.dispose()


def drop_test_schemas() -> None:
    """DROP every ``test_*`` schema CASCADE owned by the current user.

    Master-only cleanup. Idempotent (``IF EXISTS``). Catches stale
    schemas left by a crashed prior run. Schemas owned by other roles
    are skipped (a non-owner cannot DROP regardless of CREATE
    privilege).
    """
    cfg = POSTGRES_CONFIG
    user = cfg["user"]
    conn = _sync_psycopg2_connect(autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT nspname FROM pg_namespace "
                "WHERE nspname LIKE 'test\\_%%' ESCAPE '\\' "
                "AND nspowner = (SELECT oid FROM pg_roles WHERE rolname = %s)",
                (user,),
            )
            schemas = [row[0] for row in cur.fetchall()]
            for schema in schemas:
                cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                logger.debug("Dropped test schema: %s", schema)
    finally:
        conn.close()
