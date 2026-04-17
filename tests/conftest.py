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

if "POSTGRES_PASSWORD" not in os.environ:
    raise EnvironmentError(
        "POSTGRES_PASSWORD 环境变量未设置。请在 .env 文件或系统环境变量中配置。"
    )

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


async def _delete_test_user_async(session, user_id, username):
    """Delete a test user and all FK-dependent rows.

    Handles ALL known FK dependencies consistently with clean_db
    and pytest_sessionfinish.
    """
    from sqlalchemy import text

    # user_id FK tables (comprehensive list matching clean_db)
    for table in [
        "products",
        "active_sessions",
        "logistics",
        "payment_orders",
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
                text(f"DELETE FROM {table} WHERE user_id = :uid"),
                {"uid": user_id},
            )
        except Exception:
            pass

    # identifier FK tables (username-based)
    for table in ["login_attempts", "user_lockouts"]:
        try:
            await session.execute(
                text(f"DELETE FROM {table} WHERE identifier = :uname"),
                {"uname": username},
            )
        except Exception:
            pass

    # admin_action_log references both admin_id and target_user_id
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

    # audit_logs references admin_id
    try:
        await session.execute(
            text("DELETE FROM audit_logs WHERE admin_id = :uid"),
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
                            "DELETE FROM audit_logs"
                            f" WHERE admin_id IN ({test_user_subquery})"
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
