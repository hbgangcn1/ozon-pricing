# -*- coding: utf-8 -*-
"""
根目录的pytest配置文件
用于排除非测试文件
"""

import os
import sys
import types
from pathlib import Path

os.environ["E2E_TEST"] = "1"
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-do-not-use-in-production")


def pytest_ignore_collect(collection_path, config):
    _ = config
    if isinstance(collection_path, Path):
        if collection_path.suffix == ".txt":
            return True
    else:
        if str(collection_path).endswith(".txt"):
            return True
    return None


def _mock_redis_cache_module() -> None:
    try:
        if "redis_cache" not in sys.modules:
            return
        mod = sys.modules["redis_cache"]
        if not hasattr(mod, "_original_get_redis_client"):
            setattr(
                mod,
                "_original_get_redis_client",
                getattr(mod, "get_redis_client", None),
            )
        if not hasattr(mod, "_original_init_redis_client"):
            setattr(
                mod,
                "_original_init_redis_client",
                getattr(mod, "init_redis_client", None),
            )
        setattr(mod, "get_redis_client", lambda: None)
        setattr(mod, "REDIS_AVAILABLE", False)
        setattr(mod, "init_redis_client", lambda *a, **k: False)
        if hasattr(mod, "_redis_client"):
            setattr(mod, "_redis_client", None)
    except (KeyError, AttributeError):
        pass


def _build_fake_backup_system(backup_dir: str = "backups") -> types.SimpleNamespace:
    return types.SimpleNamespace(
        is_running=False,
        backup_dir=backup_dir,
        db_path="pricing_system.db",
        backup_interval_hours=6,
        max_backups=28,
        backup_thread=None,
        create_backup=lambda: True,
        restore_from_backup=lambda *a, **k: True,
        delete_backup=lambda *a, **k: True,
        verify_backup=lambda *a, **k: True,
        read_backup_file=lambda *a, **k: b"fake_backup_data",
        get_backup_stats=lambda: None,
        cleanup_old_backups=lambda: None,
        get_backup_file_path=lambda *a, **k: "fake_path",
        start_auto_backup=lambda: None,
        stop_auto_backup=lambda: None,
        manual_backup=lambda: True,
        list_backups=lambda: [],
    )


def _mock_auto_backup_module() -> None:
    try:
        import auto_backup
    except ImportError:
        return
    auto_backup.backup_system = _build_fake_backup_system()
    auto_backup.create_manual_backup = lambda: True
    auto_backup.restore_database = lambda *a, **k: True
    auto_backup.delete_backup_file = lambda *a, **k: True
    auto_backup.verify_backup_file = lambda *a, **k: True
    auto_backup.read_backup_file = lambda *a, **k: b"fake_data"
    auto_backup.list_backup_files = lambda: []
    auto_backup.get_auto_backup_settings = lambda: {
        "enabled": False,
        "interval_hours": 24,
        "max_backups": 10,
    }
    auto_backup.get_backup_info = lambda: None
    auto_backup.update_auto_backup_settings = lambda *a, **k: None
    auto_backup.start_backup_service = lambda: None
    auto_backup.stop_backup_service = lambda: None


def _mock_postgres_backup_service_module() -> None:
    try:
        import postgres_backup_service
    except (ImportError, AttributeError):
        return
    try:
        if hasattr(postgres_backup_service, "backup_system"):
            postgres_backup_service.backup_system = _build_fake_backup_system(
                backup_dir="backups/postgres"
            )

        function_overrides = {
            "restore_database": lambda *a, **k: True,
            "create_manual_backup": lambda: True,
            "delete_backup_file": lambda *a, **k: True,
            "verify_backup_file": lambda *a, **k: True,
            "read_backup_file": lambda *a, **k: b"fake_data",
            "list_backup_files": lambda: [],
            "get_auto_backup_settings": lambda: {
                "enabled": False,
                "interval_hours": 24,
                "max_backups": 10,
            },
            "get_backup_info": lambda: None,
            "update_auto_backup_settings": lambda *a, **k: None,
            "start_backup_service": lambda: None,
            "stop_backup_service": lambda: None,
        }
        for name, fn in function_overrides.items():
            if hasattr(postgres_backup_service, name):
                setattr(postgres_backup_service, name, fn)
    except AttributeError:
        pass


def pytest_sessionstart(session):
    _ = session
    _mock_redis_cache_module()
    _mock_auto_backup_module()
    _mock_postgres_backup_service_module()


_TEST_USER_ID_SUBQUERY = (
    "SELECT id FROM users "
    "WHERE (is_test_user = 1 OR username LIKE 'test_%%'"
    " OR username LIKE 'e2e%%') AND id != 1"
)
_TEST_USER_NAME_SUBQUERY = (
    "SELECT username FROM users "
    "WHERE (is_test_user = 1 OR username LIKE 'test_%%'"
    " OR username LIKE 'e2e%%') AND id != 1"
)


def _delete_by_user_id(cursor, conn, table: str) -> None:
    try:
        cursor.execute(
            f"DELETE FROM {table} WHERE user_id IN ({_TEST_USER_ID_SUBQUERY})"
        )
    except Exception as exc:
        print(f"[pytest_sessionfinish] cleanup {table} failed: {exc}")
        conn.rollback()


def _delete_by_identifier(cursor, conn, table: str) -> None:
    try:
        cursor.execute(
            f"DELETE FROM {table} WHERE identifier IN ({_TEST_USER_NAME_SUBQUERY})"
        )
    except Exception as exc:
        print(f"[pytest_sessionfinish] cleanup {table} failed: {exc}")
        conn.rollback()


def _cleanup_admin_audit_tables(cursor, conn) -> None:
    try:
        cursor.execute(
            f"DELETE FROM admin_action_log"
            f" WHERE admin_id IN ({_TEST_USER_ID_SUBQUERY})"
            f" OR target_user_id IN ({_TEST_USER_ID_SUBQUERY})"
        )
    except Exception as exc:
        print(f"[pytest_sessionfinish] cleanup admin_action_log failed: {exc}")
        conn.rollback()

    try:
        cursor.execute(
            f"DELETE FROM audit_logs WHERE admin_id IN ({_TEST_USER_ID_SUBQUERY})"
        )
    except Exception as exc:
        print(f"[pytest_sessionfinish] cleanup audit_logs failed: {exc}")
        conn.rollback()


def _cleanup_test_users(conn) -> None:
    cursor = conn.cursor()

    for table in ["products", "logistics", "payment_orders", "active_sessions"]:
        _delete_by_user_id(cursor, conn, table)

    for table in ["login_attempts", "user_lockouts"]:
        _delete_by_identifier(cursor, conn, table)

    for table in [
        "user_login_log",
        "user_behavior_log",
        "subscription_upgrade_history",
        "trusted_devices",
        "commission_category",
    ]:
        _delete_by_user_id(cursor, conn, table)

    _cleanup_admin_audit_tables(cursor, conn)

    cursor.execute(
        "DELETE FROM users"
        " WHERE (is_test_user = 1 OR username LIKE 'test_%%'"
        " OR username LIKE 'e2e%%') AND id != 1"
        " RETURNING id"
    )
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()

    if deleted > 0:
        print(
            f"\n[pytest_sessionfinish] Cleaned up {deleted}"
            " orphaned test user(s)."
        )


def pytest_sessionfinish(session, exitstatus):
    _ = session
    _ = exitstatus
    try:
        import psycopg2

        with psycopg2.connect(
            host="localhost",
            port=5432,
            dbname="logistics",
            user="postgres",
            password=os.environ.get("POSTGRES_PASSWORD", ""),
        ) as conn:
            conn.autocommit = False
            _cleanup_test_users(conn)
    except Exception as exc:
        print(f"[pytest_sessionfinish] global cleanup FAILED: {exc}")
