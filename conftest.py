# -*- coding: utf-8 -*-
"""
根目录的pytest配置文件
用于排除非测试文件
"""

import os
import types
from pathlib import Path

os.environ["E2E_TEST"] = "1"
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-do-not-use-in-production")

_original_import_module_fn = None


def pytest_ignore_collect(collection_path, config):
    """忽略收集某些文件"""
    _ = config  # 保留参数占位，便于未来扩展
    if isinstance(collection_path, Path):
        if collection_path.suffix == ".txt":
            return True
    else:
        # 兼容旧版本pytest的py.path.local
        if str(collection_path).endswith(".txt"):
            return True
    return None


def pytest_sessionstart(session):
    """
    在测试会话开始时 mock 所有备份相关操作
    避免测试中执行真实的数据库备份/恢复操作，大幅提升测试速度
    """
    _ = session  # 参数保留，用于未来扩展

    # 在测试会话开始时立即设置 session_security_enhanced mock
    # 这确保在任何模块导入之前就设置好 mock
    import sys
    from types import ModuleType
    from unittest.mock import MagicMock

    # 创建假的 SessionSecurityEnhanced 类
    fake_enhanced_class = MagicMock()
    fake_enhanced_class.check_and_create_session_atomic = MagicMock(
        return_value=(False, "Mocked: enhanced module not available")
    )

    # 创建假的模块
    fake_enhanced_module = ModuleType("session_security_enhanced")
    setattr(fake_enhanced_module, "SessionSecurityEnhanced", fake_enhanced_class)

    # 立即插入到 sys.modules（在任何导入之前）
    sys.modules["session_security_enhanced"] = fake_enhanced_module
    sys.modules["logistics.session_security_enhanced"] = fake_enhanced_module

    # Mock importlib.import_module 来拦截所有导入尝试
    import importlib

    original_import_module = importlib.import_module

    def mock_import_module(name, package=None):
        if name == "session_security_enhanced" or (
            package
            and (
                name.endswith(".session_security_enhanced")
                or name == ".session_security_enhanced"
            )
        ):
            return fake_enhanced_module
        return original_import_module(name, package)

    # 替换 importlib.import_module
    importlib.import_module = mock_import_module
    global _original_import_module_fn
    _original_import_module_fn = original_import_module

    # Mock redis_cache.get_redis_client 以防止 Redis 连接超时
    # 这必须在导入任何可能使用 Redis 的模块之前完成
    # 注意：不在根 conftest.py 中预插入假的 redis_cache 模块
    # 因为这会影响 test_redis_cache.py 的导入
    # 实际的 mock 会在 tests/conftest.py 的 pytest_runtest_setup 中处理
    #
    # 但是，我们需要在 pytest_sessionstart 中就尝试 mock redis_cache（如果它已经被导入）
    # 以防止在完整测试套件中，某些模块在导入时尝试连接 Redis
    try:
        if "redis_cache" in sys.modules:
            redis_cache_mod = sys.modules["redis_cache"]
            # 保存原始函数（如果还没有保存）
            if not hasattr(redis_cache_mod, "_original_get_redis_client"):
                setattr(
                    redis_cache_mod,
                    "_original_get_redis_client",
                    getattr(redis_cache_mod, "get_redis_client", None),
                )
            if not hasattr(redis_cache_mod, "_original_init_redis_client"):
                setattr(
                    redis_cache_mod,
                    "_original_init_redis_client",
                    getattr(redis_cache_mod, "init_redis_client", None),
                )
            # Mock get_redis_client 返回 None，避免连接尝试
            setattr(redis_cache_mod, "get_redis_client", lambda: None)
            # 确保 REDIS_AVAILABLE 为 False，避免其他代码尝试使用 Redis
            setattr(redis_cache_mod, "REDIS_AVAILABLE", False)
            # Mock init_redis_client 返回 False，避免初始化尝试
            setattr(redis_cache_mod, "init_redis_client", lambda *args, **kwargs: False)
            # 确保 _redis_client 为 None
            if hasattr(redis_cache_mod, "_redis_client"):
                setattr(redis_cache_mod, "_redis_client", None)
    except (KeyError, AttributeError):
        # redis_cache 模块不存在或无法访问，跳过
        pass
    # 创建 mock 的备份系统对象，包含所有必需的属性和方法
    fake_backup_system = types.SimpleNamespace(
        is_running=False,
        backup_dir="backups",  # 必需的属性
        db_path="pricing_system.db",  # 必需的属性
        backup_interval_hours=6,  # 必需的属性
        max_backups=28,  # 必需的属性
        backup_thread=None,  # 必需的属性
        create_backup=lambda: True,
        restore_from_backup=lambda *a, **k: True,
        delete_backup=lambda *a, **k: True,
        verify_backup=lambda *a, **k: True,
        read_backup_file=lambda *a, **k: b"fake_backup_data",
        get_backup_stats=lambda: None,
        cleanup_old_backups=lambda: None,  # 必需的方法
        get_backup_file_path=lambda *a, **k: "fake_path",  # 必需的方法
        start_auto_backup=lambda: None,  # 必需的方法
        stop_auto_backup=lambda: None,  # 必需的方法
        manual_backup=lambda: True,  # 必需的方法
        list_backups=lambda: [],  # 必需的方法（PostgreSQL）
    )

    # Mock auto_backup 模块的所有函数和对象
    try:
        import auto_backup

        auto_backup.backup_system = fake_backup_system
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
        # Mock start/stop 函数
        auto_backup.start_backup_service = lambda: None
        auto_backup.stop_backup_service = lambda: None
    except ImportError:
        auto_backup = None  # noqa: F841

    # 如果使用 PostgreSQL，也需要 mock postgres_backup_service
    try:
        import postgres_backup_service

        # Mock postgres_backup_service 的 backup_system 对象
        if hasattr(postgres_backup_service, "backup_system"):
            pg_fake_system = types.SimpleNamespace(
                restore_from_backup=lambda *a, **k: True,
                create_backup=lambda: True,
                delete_backup=lambda *a, **k: True,
                verify_backup=lambda *a, **k: True,
                read_backup_file=lambda *a, **k: b"fake_data",
                get_backup_stats=lambda: None,
                is_running=False,
                backup_dir="backups/postgres",  # 必需的属性
                backup_interval_hours=6,  # 必需的属性
                max_backups=28,  # 必需的属性
                backup_thread=None,  # 必需的属性
                cleanup_old_backups=lambda: None,  # 必需的方法
                get_backup_file_path=lambda *a, **k: "fake_path",  # 必需的方法
                list_backups=lambda: [],  # 必需的方法
            )
            postgres_backup_service.backup_system = pg_fake_system

        # Mock postgres_backup_service 模块级别的函数
        if hasattr(postgres_backup_service, "restore_database"):
            postgres_backup_service.restore_database = lambda *a, **k: True
        if hasattr(postgres_backup_service, "create_manual_backup"):
            postgres_backup_service.create_manual_backup = lambda: True
        if hasattr(postgres_backup_service, "delete_backup_file"):
            postgres_backup_service.delete_backup_file = lambda *a, **k: True
        if hasattr(postgres_backup_service, "verify_backup_file"):
            postgres_backup_service.verify_backup_file = lambda *a, **k: True
        if hasattr(postgres_backup_service, "read_backup_file"):
            postgres_backup_service.read_backup_file = lambda *a, **k: b"fake_data"
        if hasattr(postgres_backup_service, "list_backup_files"):
            postgres_backup_service.list_backup_files = lambda: []
        if hasattr(postgres_backup_service, "get_auto_backup_settings"):
            postgres_backup_service.get_auto_backup_settings = lambda: {
                "enabled": False,
                "interval_hours": 24,
                "max_backups": 10,
            }
        if hasattr(postgres_backup_service, "get_backup_info"):
            postgres_backup_service.get_backup_info = lambda: None
        if hasattr(postgres_backup_service, "update_auto_backup_settings"):
            postgres_backup_service.update_auto_backup_settings = lambda *a, **k: None
        # Mock start/stop 函数
        if hasattr(postgres_backup_service, "start_backup_service"):
            postgres_backup_service.start_backup_service = lambda: None
        if hasattr(postgres_backup_service, "stop_backup_service"):
            postgres_backup_service.stop_backup_service = lambda: None
    except (ImportError, AttributeError):
        postgres_backup_service = None  # noqa: F841


def pytest_sessionfinish(session, exitstatus):
    _ = session
    _ = exitstatus

    # 恢复 importlib.import_module
    import importlib
    global _original_import_module_fn
    if _original_import_module_fn is not None:
        importlib.import_module = _original_import_module_fn
        _original_import_module_fn = None

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
            c = conn.cursor()

            test_user_subquery = (
                "SELECT id FROM users "
                "WHERE (is_test_user = 1 OR username LIKE 'test_%%'"
                " OR username LIKE 'e2e%%') AND id != 1"
            )
            test_name_subquery = (
                "SELECT username FROM users "
                "WHERE (is_test_user = 1 OR username LIKE 'test_%%'"
                " OR username LIKE 'e2e%%') AND id != 1"
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
                except Exception as exc:
                    print(f"[pytest_sessionfinish] cleanup {table} failed: {exc}")
                    conn.rollback()

            for table in ["login_attempts", "user_lockouts"]:
                try:
                    c.execute(
                        f"DELETE FROM {table} WHERE identifier IN ({test_name_subquery})"
                    )
                except Exception as exc:
                    print(f"[pytest_sessionfinish] cleanup {table} failed: {exc}")
                    conn.rollback()

            for table in [
                "user_login_log",
                "user_behavior_log",
                "subscription_upgrade_history",
                "trusted_devices",
                "commission_category",
            ]:
                try:
                    c.execute(
                        f"DELETE FROM {table} WHERE user_id IN ({test_user_subquery})"
                    )
                except Exception as exc:
                    print(f"[pytest_sessionfinish] cleanup {table} failed: {exc}")
                    conn.rollback()

            try:
                c.execute(
                    f"DELETE FROM admin_action_log"
                    f" WHERE admin_id IN ({test_user_subquery})"
                    f" OR target_user_id IN ({test_user_subquery})"
                )
            except Exception as exc:
                print(f"[pytest_sessionfinish] cleanup admin_action_log failed: {exc}")
                conn.rollback()

            try:
                c.execute(
                    f"DELETE FROM audit_logs WHERE admin_id IN ({test_user_subquery})"
                )
            except Exception as exc:
                print(f"[pytest_sessionfinish] cleanup audit_logs failed: {exc}")
                conn.rollback()

            c.execute(
                "DELETE FROM users"
                " WHERE (is_test_user = 1 OR username LIKE 'test_%%'"
                " OR username LIKE 'e2e%%') AND id != 1"
                " RETURNING id"
            )
            deleted = c.rowcount
            conn.commit()

            if deleted > 0:
                print(
                    f"\n[pytest_sessionfinish] Cleaned up {deleted}"
                    " orphaned test user(s)."
                )
    except Exception as exc:
        print(f"[pytest_sessionfinish] global cleanup FAILED: {exc}")
