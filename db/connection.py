import atexit
import logging
import os
import signal
import sys
import threading

from db._proxy import _db

logger = logging.getLogger(__name__)

_connection_counter = 0
_connection_lock = threading.Lock()
_MAX_CONNECTIONS = 50
_postgres_pool_closed_logged = False

_CONNECTION_WARNINGS = set()
_WARNING_THRESHOLD = 10
_CRITICAL_THRESHOLD = 30


def _get_pkg():
    """Get the db package module directly (not via proxy)."""
    import db

    return db


def _get_counter():
    return getattr(_get_pkg(), "_connection_counter", _connection_counter)


def _set_counter(val):
    try:
        setattr(_get_pkg(), "_connection_counter", val)
    except (AttributeError, TypeError):
        pass


def _get_warnings():
    return getattr(_get_pkg(), "_CONNECTION_WARNINGS", _CONNECTION_WARNINGS)


def _increment_connection_counter():
    with _connection_lock:
        _set_counter(_get_counter() + 1)
        current_count = _get_counter()
        warnings = _get_warnings()

        if current_count > _CRITICAL_THRESHOLD:
            if "critical" not in warnings:
                print(
                    f"🚨 严重警告: 当前活跃连接数 {current_count} "
                    f"超过严重阈值 {_CRITICAL_THRESHOLD}"
                )
                warnings.add("critical")
        elif current_count > _WARNING_THRESHOLD:
            if "warning" not in warnings:
                print(
                    f"⚠️  警告: 当前活跃连接数 {current_count} "
                    f"超过警告阈值 {_WARNING_THRESHOLD}"
                )
                warnings.add("warning")
        else:
            warnings.clear()

        return current_count


def _decrement_connection_counter():
    with _connection_lock:
        _set_counter(max(0, _get_counter() - 1))
        current_count = _get_counter()
        warnings = _get_warnings()

        if current_count <= _WARNING_THRESHOLD:
            warnings.clear()

        return current_count


def get_connection_count():
    with _connection_lock:
        return _get_counter()


def reset_connection_counter():
    with _connection_lock:
        _set_counter(0)
        _get_warnings().clear()


def get_connection_stats():
    with _connection_lock:
        return {
            "active_connections": _get_counter(),
            "max_connections": _MAX_CONNECTIONS,
            "warning_threshold": _WARNING_THRESHOLD,
            "critical_threshold": _CRITICAL_THRESHOLD,
            "warnings_active": len(_get_warnings()) > 0,
        }


def _check_connections_at_exit():
    try:
        count = _db.get_connection_count()
    except (AttributeError, RuntimeError, TypeError):
        count = 0
    skip_cleanup = os.getenv("DBUTILS_SKIP_EXIT_CLEANUP") == "1"

    if count > 0:
        print(f"⚠️  警告: 程序退出时仍有 {count} 个数据库连接未关闭")
        print("🔧 正在强制关闭所有连接...")

    if not skip_cleanup:
        try:
            from db_adapter import close_connection_pool
        except ImportError:

            def close_connection_pool():
                pass

        try:
            close_connection_pool()
            pkg = _get_pkg()
            pg_logged = getattr(pkg, "_postgres_pool_closed_logged", False)
            if not pg_logged:
                print("✅ PostgreSQL连接池已关闭")
                try:
                    setattr(pkg, "_postgres_pool_closed_logged", True)
                except (AttributeError, TypeError):
                    pass
        except (AttributeError, RuntimeError, OSError, ConnectionError):
            pass

    try:
        with _connection_lock:
            remaining_count = _get_counter()
            if remaining_count > 0:
                print(f"⚠️  仍有 {remaining_count} 个连接未通过正常流程关闭")
            _set_counter(0)
    except (AttributeError, RuntimeError):
        _set_counter(0)


def _cleanup_on_interrupt():
    print("\n🛑 收到中断信号，正在优雅关闭...")
    _db._check_connections_at_exit()
    print("✅ 数据库连接已清理完成")


atexit.register(_check_connections_at_exit)


def signal_handler(signum, frame):
    _ = signum, frame
    _db._cleanup_on_interrupt()
    sys.exit(0)


try:
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
except (ValueError, OSError):
    pass


def get_db_connection():
    from db_adapter import get_db_connection as _adapter_func

    return _adapter_func()


def get_db():
    return _db.get_db_connection()


class DBConnection:
    def __init__(self):
        self._conn = None

    def __enter__(self):
        self._conn = _db.get_db_connection()
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            self._conn.close()
        return False


def get_enhanced_db_connection():
    try:
        from .enhanced_connection_manager import get_enhanced_db_connection

        return get_enhanced_db_connection()
    except ImportError:
        print("警告: 增强连接管理器不可用，使用标准连接")
        return _db.get_db_connection()


def get_enhanced_connection_stats():
    try:
        from .enhanced_connection_manager import get_connection_stats as enhanced_stats

        return enhanced_stats()
    except ImportError:
        return _db.get_connection_stats()
