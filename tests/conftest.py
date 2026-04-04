"""
测试配置文件 - FastAPI + PostgreSQL (async SQLAlchemy ORM)
"""

import os
import sys
import time
import warnings

import pytest

os.environ["DB_TYPE"] = "postgresql"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_DB"] = "logistics"
os.environ["POSTGRES_USER"] = "postgres"
if "POSTGRES_PASSWORD" not in os.environ:
    os.environ["POSTGRES_PASSWORD"] = "***REMOVED-PG-PWD***"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

warnings.filterwarnings("ignore", category=ResourceWarning)


async def _delete_test_user_async(session, user_id, username):
    """Delete a test user and all FK-dependent rows."""
    from sqlalchemy import text

    for table, col in [
        ("products", "user_id"),
        ("active_sessions", "user_id"),
        ("logistics", "user_id"),
        ("payment_orders", "user_id"),
    ]:
        try:
            await session.execute(
                text(f"DELETE FROM {table} WHERE {col} = :uid"),
                {"uid": user_id},
            )
        except Exception:
            pass

    for table, col in [
        ("login_attempts", "identifier"),
        ("user_lockouts", "identifier"),
    ]:
        try:
            await session.execute(
                text(f"DELETE FROM {table} WHERE {col} = :uname"),
                {"uname": username},
            )
        except Exception:
            pass

    for table, col in [
        ("user_login_log", "user_id"),
        ("user_behavior_log", "user_id"),
        ("subscription_upgrade_history", "user_id"),
    ]:
        try:
            await session.execute(
                text(f"DELETE FROM {table} WHERE {col} = :uid"),
                {"uid": user_id},
            )
        except Exception:
            pass

    try:
        await session.execute(
            text(
                "DELETE FROM admin_action_log"
                " WHERE admin_id = :uid OR target_user_id = :uid"
            ),
            {"uid": user_id},
        )
    except Exception:
        pass

    await session.execute(
        text("DELETE FROM users WHERE id = :uid"),
        {"uid": user_id},
    )


@pytest.fixture
async def db_session():
    """Provide an async SQLAlchemy session for tests."""
    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


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

    username = f"test_user_{int(time.time() * 1000)}"
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

    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as cleanup_session:
        try:
            await _delete_test_user_async(cleanup_session, user_id, username)
            await cleanup_session.commit()
        except Exception:
            await cleanup_session.rollback()


@pytest.fixture
async def test_admin(db_session):
    """创建测试管理员用户，测试后自动清理"""
    from db.password import hash_password
    from models.user import User

    username = f"test_admin_{int(time.time() * 1000)}"
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

    from database import AsyncSessionLocal

    async with AsyncSessionLocal() as cleanup_session:
        try:
            await _delete_test_user_async(cleanup_session, user_id, username)
            await cleanup_session.commit()
        except Exception:
            await cleanup_session.rollback()


@pytest.fixture
async def clean_db():
    """清理数据库中的测试数据"""
    from database import AsyncSessionLocal
    from sqlalchemy import text

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
                    try:
                        await session.execute(
                            text(
                                f"DELETE FROM {table}"
                                f" WHERE user_id IN ({test_user_subquery})"
                            )
                        )
                    except Exception:
                        pass
                for table in ["login_attempts", "user_lockouts"]:
                    try:
                        await session.execute(
                            text(
                                f"DELETE FROM {table}"
                                f" WHERE identifier IN ({test_name_subquery})"
                            )
                        )
                    except Exception:
                        pass
                for table in [
                    "logistics_pricing_rules",
                    "pricing_plans",
                    "orders",
                    "session_security_audit_log",
                    "user_sessions",
                    "rate_limit_log",
                    "user_login_log",
                    "user_behavior_log",
                    "subscription_upgrade_history",
                ]:
                    try:
                        await session.execute(
                            text(
                                f"DELETE FROM {table}"
                                f" WHERE user_id IN ({test_user_subquery})"
                            )
                        )
                    except Exception:
                        pass
                try:
                    await session.execute(
                        text(
                            "DELETE FROM admin_action_log"
                            f" WHERE admin_id IN ({test_user_subquery})"
                            f" OR target_user_id IN ({test_user_subquery})"
                        )
                    )
                except Exception:
                    pass
                try:
                    await session.execute(
                        text(
                            "DELETE FROM users"
                            " WHERE is_test_user = 1"
                            " OR username LIKE 'test_%%'"
                            " OR username LIKE 'e2e%%'"
                        )
                    )
                except Exception:
                    pass
                await session.commit()
            except Exception:
                await session.rollback()

    await _clean()
    yield
    await _clean()


# Backward compat alias
_clean_db = clean_db
