"""
测试配置文件 - FastAPI + PostgreSQL (async SQLAlchemy ORM)
"""

import os
import sys
import time
import warnings
from pathlib import Path

import bcrypt
import pytest

# 从项目根目录 .env 加载环境变量（不覆盖已有值）
_project_root = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv

    load_dotenv(_project_root / ".env")
except ImportError:
    pass  # python-dotenv 不可用时依赖系统环境变量

os.environ.setdefault("DB_TYPE", "postgresql")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "logistics")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-jwt-refresh-option-a-1234567890")
os.environ.setdefault("ALLOWED_ORIGINS", "http://test")

if "POSTGRES_PASSWORD" not in os.environ:
    raise EnvironmentError(
        "POSTGRES_PASSWORD 环境变量未设置。请在 .env 文件或系统环境变量中配置。"
    )

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _install_worker_schema_isolation() -> None:
    import database
    from tests._db_isolation import (
        create_all_in_schema,
        create_worker_schema,
        make_worker_engine,
        make_worker_sessionmaker,
        worker_schema_name,
    )

    schema = worker_schema_name()
    create_worker_schema(schema)
    create_all_in_schema(schema)

    worker_engine = make_worker_engine(schema)
    worker_sessionmaker = make_worker_sessionmaker(worker_engine)

    database.engine = worker_engine
    database.AsyncSessionLocal = worker_sessionmaker


_install_worker_schema_isolation()

warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings(
    "ignore",
    message="Support for class-based.*",
    category=DeprecationWarning,
)

# --- 性能优化: 降低 bcrypt rounds 从12 到 4 ---
_original_gensalt = bcrypt.gensalt


def _fast_gensalt(rounds=12, prefix=b"2b"):
    return _original_gensalt(rounds=4, prefix=prefix)


bcrypt.gensalt = _fast_gensalt


async def _safe_cleanup_execute(session, statement, params):
    """Execute best-effort cleanup SQL without poisoning the session."""
    from sqlalchemy import text

    try:
        await session.execute(text(statement), params)
    except Exception:
        await session.rollback()


async def _delete_test_user_async(session, user_id, username):
    """Delete a test user and all FK-dependent rows.

    Handles ALL known FK dependencies consistently with clean_db
    and pytest_sessionfinish.
    """
    # user_id FK tables (ORM-registered only; legacy non-ORM tables removed
    # per fix-pytest-xdist-isolation Phase 3.4 set-diff)
    for table in [
        "products",
        "active_sessions",
        "logistics",
        "payment_orders",
        "user_login_log",
        "user_behavior_log",
        "subscription_upgrade_history",
        "trial_overflow_window",
    ]:
        await _safe_cleanup_execute(
            session,
            f"DELETE FROM {table} WHERE user_id = :uid",
            {"uid": user_id},
        )

    # identifier FK tables (username-based)
    for table in ["login_attempts", "user_lockouts"]:
        await _safe_cleanup_execute(
            session,
            f"DELETE FROM {table} WHERE identifier = :uname",
            {"uname": username},
        )

    # admin_action_log references both admin_id and target_user_id
    await _safe_cleanup_execute(
        session,
        "DELETE FROM admin_action_log"
        " WHERE admin_id = :uid OR target_user_id = :uid",
        {"uid": user_id},
    )

    # audit_logs references admin_id
    await _safe_cleanup_execute(
        session,
        "DELETE FROM audit_logs WHERE admin_id = :uid",
        {"uid": user_id},
    )
    await _safe_cleanup_execute(
        session,
        "DELETE FROM users WHERE id = :uid",
        {"uid": user_id},
    )


@pytest.fixture
async def db_session():
    """Provide an async SQLAlchemy session for tests."""
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()

    # Clean committed test users that rollback cannot undo
    async with AsyncSessionLocal() as cleanup:
        try:
            from sqlalchemy import text

            ids_q = "SELECT id, username FROM users WHERE is_test_user = 1"
            rows = (await cleanup.execute(text(ids_q))).fetchall()
            for uid, uname in rows:
                await _delete_test_user_async(cleanup, uid, uname)
            await cleanup.commit()
        except Exception as exc:
            print(f"[db_session cleanup] FAILED: {exc}")
            await cleanup.rollback()


@pytest.fixture
async def client():
    """Provide an async test client with dependency overrides."""
    from httpx import AsyncClient, ASGITransport
    from api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_user(db_session):
    """创建测试用户，测试后自动清理"""
    from db.password import hash_password
    from models.user import User

    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
    username = f"test_user_{worker_id}_{int(time.time() * 1000)}_{os.getpid()}"
    password = "TestP@ss123456"
    hashed = hash_password(password)

    user = User(
        username=username,
        password=hashed,
        role="user",
        user_type="free",
        subscription_type="free",
        remaining_calculations=10,
        created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        is_test_user=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()

    user_id = user.id
    yield {"id": user_id, "username": username, "password": password}

    # Release any row locks held by db_session before cleanup
    await db_session.rollback()

    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as cleanup_session:
        try:
            await _delete_test_user_async(cleanup_session, user_id, username)
            await cleanup_session.commit()
        except Exception as exc:
            print(f"[test_user cleanup] FAILED for {username}: {exc}")
            await cleanup_session.rollback()


@pytest.fixture
async def test_admin(db_session):
    """创建测试管理员用户，测试后自动清理"""
    from db.password import hash_password
    from models.user import User

    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
    username = f"test_admin_{worker_id}_{int(time.time() * 1000)}_{os.getpid()}"
    password = "AdminP@ss123456"
    hashed = hash_password(password)

    user = User(
        username=username,
        password=hashed,
        role="admin",
        user_type="permanent",
        subscription_type="free",
        remaining_calculations=-1,
        created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        is_test_user=1,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()

    user_id = user.id
    yield {"id": user_id, "username": username, "password": password}

    # Release any row locks held by db_session before cleanup
    await db_session.rollback()

    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as cleanup_session:
        try:
            await _delete_test_user_async(cleanup_session, user_id, username)
            await cleanup_session.commit()
        except Exception as exc:
            print(f"[test_admin cleanup] FAILED for {username}: {exc}")
            await cleanup_session.rollback()


@pytest.fixture
async def clean_db():
    """清理数据库中的测试数据"""
    from database import AsyncSessionLocal

    async def _clean():
        async with AsyncSessionLocal() as session:
            try:
                test_user_subquery = (
                    "SELECT id FROM users"
                    " WHERE is_test_user = 1"
                    " OR username LIKE 'test_%%'"
                    " OR username LIKE 'e2e%%'"
                )
                test_name_subquery = (
                    "SELECT username FROM users"
                    " WHERE is_test_user = 1"
                    " OR username LIKE 'test_%%'"
                    " OR username LIKE 'e2e%%'"
                )
                for table in [
                    "products",
                    "logistics",
                    "payment_orders",
                    "active_sessions",
                ]:
                    await _safe_cleanup_execute(
                        session,
                        f"DELETE FROM {table}"
                        f" WHERE user_id IN ({test_user_subquery})",
                        {},
                    )
                for table in ["login_attempts", "user_lockouts"]:
                    await _safe_cleanup_execute(
                        session,
                        f"DELETE FROM {table}"
                        f" WHERE identifier IN ({test_name_subquery})",
                        {},
                    )
                for table in [
                    "user_login_log",
                    "user_behavior_log",
                    "subscription_upgrade_history",
                ]:
                    await _safe_cleanup_execute(
                        session,
                        f"DELETE FROM {table}"
                        f" WHERE user_id IN ({test_user_subquery})",
                        {},
                    )
                await _safe_cleanup_execute(
                    session,
                    "DELETE FROM admin_action_log"
                    f" WHERE admin_id IN ({test_user_subquery})"
                    f" OR target_user_id IN ({test_user_subquery})",
                    {},
                )
                await _safe_cleanup_execute(
                    session,
                    "DELETE FROM audit_logs"
                    f" WHERE admin_id IN ({test_user_subquery})",
                    {},
                )
                await _safe_cleanup_execute(
                    session,
                    "DELETE FROM users"
                    " WHERE is_test_user = 1"
                    " OR username LIKE 'test_%%'"
                    " OR username LIKE 'e2e%%'",
                    {},
                )
                await session.commit()
            except Exception:
                await session.rollback()

    await _clean()
    yield
    await _clean()


# Backward compat alias
_clean_db = clean_db
