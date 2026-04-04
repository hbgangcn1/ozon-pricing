"""
测试配置文件 - FastAPI + PostgreSQL
"""

import os
import sys
import time
import uuid
import warnings
from contextlib import contextmanager
from typing import Any

import pytest

os.environ["DB_TYPE"] = "postgresql"
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_DB"] = "logistics"
os.environ["POSTGRES_USER"] = "postgres"
os.environ["POSTGRES_PASSWORD"] = "***REMOVED-PG-PWD***"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

warnings.filterwarnings("ignore", category=ResourceWarning)


@contextmanager
def _get_psycopg_connection(autocommit: bool = False):
    """创建直接的 PostgreSQL 连接"""
    import psycopg2

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="logistics",
        user="postgres",
        password="***REMOVED-PG-PWD***",
    )
    try:
        if autocommit:
            conn.autocommit = True
        yield conn
    finally:
        conn.close()


TEST_SCHEMA_PREFIX = "test_schema_"
_current_test_schema: str | None = None


def _create_test_schema() -> str | None:
    """创建唯一的测试 schema"""
    global _current_test_schema
    schema_name = (
        f"{TEST_SCHEMA_PREFIX}{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
    )

    try:
        with _get_psycopg_connection(autocommit=True) as conn:
            c = conn.cursor()
            c.execute(f"CREATE SCHEMA {schema_name}")

            c.execute("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
            """)
            tables = [row[0] for row in c.fetchall()]

            for table_name in tables:
                try:
                    c.execute(
                        f"CREATE TABLE {schema_name}.{table_name} (LIKE public.{table_name} INCLUDING ALL)"
                    )
                except Exception:
                    pass

            for table_name in ["plans"]:
                if table_name in tables:
                    try:
                        c.execute(
                            f"INSERT INTO {schema_name}.{table_name} SELECT * FROM public.{table_name}"
                        )
                    except Exception:
                        pass

            _current_test_schema = schema_name
            return schema_name
    except Exception:
        return None


def _drop_test_schema(schema_name: str) -> None:
    """删除测试 schema"""
    try:
        with _get_psycopg_connection(autocommit=True) as conn:
            conn.cursor().execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
    except Exception:
        pass


def _delete_test_user_by_id(cursor: Any, user_id: int) -> None:
    required_fk_tables = [
        ("products", "user_id"),
        ("active_sessions", "user_id"),
        ("logistics", "user_id"),
        ("payment_orders", "user_id"),
    ]
    for table, col in required_fk_tables:
        try:
            cursor.execute(f"DELETE FROM {table} WHERE {col} = %s", (user_id,))
        except Exception:
            pass

    try:
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if row:
            username = row[0]
            for table, col in [
                ("login_attempts", "identifier"),
                ("user_lockouts", "identifier"),
            ]:
                try:
                    cursor.execute(f"DELETE FROM {table} WHERE {col} = %s", (username,))
                except Exception:
                    pass
    except Exception:
        pass

    optional_fk_tables = [
        ("user_login_log", "user_id"),
        ("user_behavior_log", "user_id"),
        ("subscription_upgrade_history", "user_id"),
    ]
    for table, col in optional_fk_tables:
        try:
            cursor.execute(f"DELETE FROM {table} WHERE {col} = %s", (user_id,))
        except Exception:
            pass

    try:
        cursor.execute(
            "DELETE FROM admin_action_log WHERE admin_id = %s OR target_user_id = %s",
            (user_id, user_id),
        )
    except Exception:
        pass

    try:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    except Exception:
        pass


@pytest.fixture(scope="session")
def test_schema():
    """会话级别的测试 schema"""
    schema = _create_test_schema()
    yield schema
    if schema:
        _drop_test_schema(schema)


@pytest.fixture(scope="function")
def test_user():
    """创建测试用户，测试后自动清理"""
    from db_utils import hash_password, get_db_connection

    username = f"test_user_{int(time.time() * 1000)}"
    password = "TestP@ss123456"
    user_id = None

    try:
        with get_db_connection() as (conn, c):
            hashed_password = hash_password(password)
            c.execute(
                """INSERT INTO users (username, password, role, user_type, subscription_type,
                remaining_calculations, created_at, is_test_user)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    username,
                    hashed_password,
                    "user",
                    "free",
                    "free",
                    10,
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    1,
                ),
            )
            user_id = c.fetchone()[0]
            conn.commit()
    except Exception:
        pass

    yield {"id": user_id, "username": username, "password": password}

    if user_id:
        try:
            with get_db_connection() as (conn, c):
                _delete_test_user_by_id(c, user_id)
                conn.commit()
        except Exception:
            pass


@pytest.fixture(scope="function")
def test_admin():
    """创建测试管理员用户，测试后自动清理"""
    from db_utils import hash_password, get_db_connection

    username = f"test_admin_{int(time.time() * 1000)}"
    password = "AdminP@ss123456"
    user_id = None

    try:
        with get_db_connection() as (conn, c):
            hashed_password = hash_password(password)
            c.execute(
                """INSERT INTO users (username, password, role, user_type, subscription_type,
                remaining_calculations, created_at, is_test_user)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    username,
                    hashed_password,
                    "admin",
                    "permanent",
                    "free",
                    -1,
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    1,
                ),
            )
            user_id = c.fetchone()[0]
            conn.commit()
    except Exception:
        pass

    yield {"id": user_id, "username": username, "password": password}

    if user_id:
        try:
            with get_db_connection() as (conn, c):
                _delete_test_user_by_id(c, user_id)
                conn.commit()
        except Exception:
            pass


@pytest.fixture(scope="function")
def clean_db():
    """清理数据库中的测试数据"""
    from db_utils import get_db_connection

    def _clean():
        try:
            with get_db_connection() as (conn, c):
                test_user_subquery = (
                    "SELECT id FROM users "
                    "WHERE is_test_user = 1 OR username LIKE 'test_%%'"
                    " OR username LIKE 'e2e%%'"
                )
                test_name_subquery = (
                    "SELECT username FROM users "
                    "WHERE is_test_user = 1 OR username LIKE 'test_%%'"
                    " OR username LIKE 'e2e%%'"
                )
                for table in [
                    "products",
                    "logistics",
                    "payment_orders",
                    "active_sessions",
                ]:
                    try:
                        c.execute(
                            f"DELETE FROM {table} WHERE user_id IN ({test_user_subquery})"
                        )
                    except Exception:
                        pass
                for table in ["login_attempts", "user_lockouts"]:
                    try:
                        c.execute(
                            f"DELETE FROM {table} WHERE identifier IN ({test_name_subquery})"
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
                        c.execute(
                            f"DELETE FROM {table} WHERE user_id IN ({test_user_subquery})"
                        )
                    except Exception:
                        pass
                try:
                    c.execute(
                        f"DELETE FROM admin_action_log WHERE admin_id IN ({test_user_subquery})"
                        f" OR target_user_id IN ({test_user_subquery})"
                    )
                except Exception:
                    pass
                try:
                    c.execute(
                        "DELETE FROM users WHERE is_test_user = 1"
                        " OR username LIKE 'test_%%'"
                        " OR username LIKE 'e2e%%'"
                    )
                except Exception:
                    pass
                conn.commit()
        except Exception:
            pass

    _clean()
    yield
    _clean()


# Backward compat alias
_clean_db = clean_db
