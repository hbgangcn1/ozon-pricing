import os
import sqlite3
import streamlit as st
import hashlib
import bcrypt
import threading
import atexit
import queue
import json
import time
import signal
import sys
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

# 导入错误处理模块
try:
    from .enhanced_error_handler import handle_database_error
except ImportError:
    from enhanced_error_handler import handle_database_error
try:
    from .password_utils import validate_password_strength
except ImportError:  # pragma: no cover - fallback for non-package execution
    from password_utils import validate_password_strength

# 数据库连接监控
_connection_counter = 0
_connection_lock = threading.Lock()
_MAX_CONNECTIONS = 50  # 最大并发连接数阈值

# 连接池配置
_POOL_SIZE = 10
_CONNECTION_POOL = queue.Queue(maxsize=_POOL_SIZE)
_POOL_LOCK = threading.Lock()

# 连接监控配置
_CONNECTION_WARNINGS = set()  # 记录已发送的警告
_WARNING_THRESHOLD = 10  # 连接数警告阈值
_CRITICAL_THRESHOLD = 30  # 连接数严重阈值


def _increment_connection_counter():
    """增加连接计数器"""
    global _connection_counter
    with _connection_lock:
        _connection_counter += 1
        current_count = _connection_counter

        # 连接数监控和告警
        if current_count > _CRITICAL_THRESHOLD:
            if 'critical' not in _CONNECTION_WARNINGS:
                print(f"🚨 严重警告: 当前活跃连接数 {current_count} "
                      f"超过严重阈值 {_CRITICAL_THRESHOLD}")
                _CONNECTION_WARNINGS.add('critical')
        elif current_count > _WARNING_THRESHOLD:
            if 'warning' not in _CONNECTION_WARNINGS:
                print(f"⚠️  警告: 当前活跃连接数 {current_count} "
                      f"超过警告阈值 {_WARNING_THRESHOLD}")
                _CONNECTION_WARNINGS.add('warning')
        else:
            # 连接数恢复正常，清除警告记录
            _CONNECTION_WARNINGS.clear()

        return current_count


def _decrement_connection_counter():
    """减少连接计数器"""
    global _connection_counter
    with _connection_lock:
        _connection_counter = max(0, _connection_counter - 1)
        current_count = _connection_counter

        # 如果连接数恢复正常，清除警告记录
        if current_count <= _WARNING_THRESHOLD:
            _CONNECTION_WARNINGS.clear()

        return current_count


def get_connection_count():
    """获取当前活跃连接数"""
    with _connection_lock:
        return _connection_counter


def reset_connection_counter():
    """重置连接计数器（用于测试）"""
    global _connection_counter
    with _connection_lock:
        _connection_counter = 0
        _CONNECTION_WARNINGS.clear()


def get_connection_stats():
    """获取连接统计信息"""
    with _connection_lock:
        pool_size = _CONNECTION_POOL.qsize()
        return {
            'active_connections': _connection_counter,
            'pool_size': pool_size,
            'max_connections': _MAX_CONNECTIONS,
            'warning_threshold': _WARNING_THRESHOLD,
            'critical_threshold': _CRITICAL_THRESHOLD,
            'warnings_active': len(_CONNECTION_WARNINGS) > 0
        }


def _check_connections_at_exit():
    """程序退出时检查并强制关闭所有连接"""
    count = get_connection_count()
    if count > 0:
        print(f"⚠️  警告: 程序退出时仍有 {count} 个数据库连接未关闭")
        print("🔧 正在强制关闭所有连接...")

    # 1. 清理SQLite连接池
    closed_count = 0
    try:
        while not _CONNECTION_POOL.empty():
            conn = _CONNECTION_POOL.get_nowait()
            try:
                conn.close()
                closed_count += 1
            except Exception as e:
                print(f"关闭SQLite连接时出错: {e}")
    except Exception as e:
        print(f"清理SQLite连接池时出错: {e}")

    if closed_count > 0:
        print(f"✅ 已关闭 {closed_count} 个SQLite连接")

    # 2. 关闭PostgreSQL连接池（如果使用）
    try:
        from db_adapter import close_connection_pool
    except ImportError:
        # 如果db_adapter不存在，定义占位函数
        def close_connection_pool():
            pass

    try:
        close_connection_pool()
        print("✅ PostgreSQL连接池已关闭")
    except Exception as e:
        print(f"关闭PostgreSQL连接池时出错: {e}")

    # 3. 重置计数器
    global _connection_counter
    with _connection_lock:
        if _connection_counter > 0:
            print(f"⚠️  仍有 {_connection_counter} 个连接未通过正常流程关闭")
            _connection_counter = 0


def _cleanup_on_interrupt():
    """优雅关闭处理器（用于信号处理）"""
    print("\n🛑 收到中断信号，正在优雅关闭...")
    _check_connections_at_exit()
    print("✅ 数据库连接已清理完成")


# 注册退出检查
atexit.register(_check_connections_at_exit)


def signal_handler(signum, frame):
    """处理SIGINT和SIGTERM信号"""
    # 明确标记未使用的参数
    _ = signum, frame
    _cleanup_on_interrupt()
    # 退出程序
    sys.exit(0)


# 注册信号处理（优雅关闭）
try:
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill命令
except (ValueError, OSError):
    # Windows上某些信号不支持，忽略
    pass


def monitor_connections():
    """连接监控函数，可在定时任务中调用"""
    stats = get_connection_stats()

    if stats['active_connections'] > _CRITICAL_THRESHOLD:
        print(f"🚨 连接数严重超限: {stats['active_connections']}/"
              f"{_CRITICAL_THRESHOLD}")
        # 这里可以添加告警通知逻辑，如发送邮件、短信等
        return 'critical'
    elif stats['active_connections'] > _WARNING_THRESHOLD:
        print(f"⚠️  连接数超限: {stats['active_connections']}/"
              f"{_WARNING_THRESHOLD}")
        return 'warning'
    else:
        print(f"✅ 连接数正常: {stats['active_connections']}")
        return 'normal'


def _create_db_connection():
    """创建新的数据库连接"""
    db_path = os.path.join(os.path.dirname(__file__), "pricing_system.db")
    conn = sqlite3.connect(
        db_path,
        check_same_thread=False,
        timeout=5.0,
    )
    # 并发与锁优化：启用 WAL、设置超时与同步级别
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
    except sqlite3.Error:
        pass
    conn.row_factory = sqlite3.Row
    return conn


def _get_connection_from_pool():
    """从连接池获取连接"""
    try:
        # 非阻塞方式获取连接
        return _CONNECTION_POOL.get_nowait()
    except queue.Empty:
        # 池中没有可用连接，创建新连接
        return _create_db_connection()


def _get_connection_with_retry(max_retries=3):
    """
    从连接池获取连接（带重试机制）

    Args:
        max_retries: 最大重试次数

    Returns:
        数据库连接对象

    Raises:
        sqlite3.OperationalError: 重试后仍然失败
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            conn = _get_connection_from_pool()
            # 测试连接是否可用
            conn.execute("SELECT 1")
            return conn
        except sqlite3.OperationalError as e:
            last_error = e
            if 'locked' in str(e).lower() and attempt < max_retries - 1:
                # 指数退避：0.1s, 0.2s, 0.4s
                wait_time = 0.1 * (2 ** attempt)
                print(f"数据库锁定，{wait_time}秒后重试 "
                      f"(尝试 {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            raise
        except Exception as e:
            # 其他异常直接抛出
            print(f"获取数据库连接失败: {e}")
            raise

    # 所有重试都失败
    raise last_error if last_error else sqlite3.OperationalError(
        "无法获取数据库连接"
    )


def _return_connection_to_pool(conn):
    """将连接返回池中"""
    try:
        # 非阻塞方式返回连接
        _CONNECTION_POOL.put_nowait(conn)
    except queue.Full:
        # 池已满，关闭连接
        conn.close()


def _initialize_connection_pool():
    """初始化连接池"""
    with _POOL_LOCK:
        if _CONNECTION_POOL.empty():
            for _ in range(_POOL_SIZE):
                try:
                    conn = _create_db_connection()
                    _CONNECTION_POOL.put_nowait(conn)
                except (Exception,) as e:
                    print(f"初始化连接池失败: {e}")


# 延迟初始化连接池
_initialize_connection_pool()


def hash_password(password: str) -> str:
    """
    使用bcrypt对密码进行加盐哈希

    Args:
        password (str): 明文密码

    Returns:
        str: 加盐哈希后的密码
    """
    # 生成随机盐值
    salt = bcrypt.gensalt(rounds=12)  # 12轮加密，安全性高
    # 对密码进行哈希
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """
    验证密码是否正确

    Args:
        password (str): 明文密码
        hashed_password (str): 存储的哈希密码

    Returns:
        bool: 密码是否正确
    """
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except (ValueError, TypeError):
        # 兼容旧的SHA256格式
        return verify_legacy_password(password, hashed_password)


def verify_legacy_password(password: str, hashed_password: str) -> bool:
    """
    验证旧的SHA256格式密码（向后兼容）

    Args:
        password (str): 明文密码
        hashed_password (str): SHA256哈希密码

    Returns:
        bool: 密码是否正确
    """
    legacy_hash = hashlib.sha256(password.encode()).hexdigest()
    return legacy_hash == hashed_password


def is_bcrypt_hash(hashed_password: str) -> bool:
    """
    检查密码是否为bcrypt格式

    Args:
        hashed_password (str): 哈希密码

    Returns:
        bool: 是否为bcrypt格式
    """
    return (hashed_password.startswith('$2b$') or
            hashed_password.startswith('$2a$'))


def get_db():
    """获取数据库连接和游标"""
    db_path = os.path.join(os.path.dirname(__file__), "pricing_system.db")
    conn = sqlite3.connect(
        db_path,
        check_same_thread=False,
        timeout=5.0,
    )
    # 并发与锁优化：启用 WAL、设置超时与同步级别
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
    except sqlite3.Error:
        pass
    conn.row_factory = sqlite3.Row

    return conn, conn.cursor()


class DBConnection:
    """显式上下文管理器，提供 (conn, cursor) 二元组（带重试机制）"""

    def __init__(self, db_path: str, max_retries=3):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._cursor: Optional[sqlite3.Cursor] = None
        self._max_retries = max_retries

    def __enter__(self) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
        last_error = None
        conn = None  # 初始化conn，避免未绑定变量错误

        for attempt in range(self._max_retries):
            try:
                conn = sqlite3.connect(
                    self._db_path,
                    check_same_thread=False,
                    timeout=5.0,
                )
                # 并发与锁优化：启用 WAL、设置超时与同步级别
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")
                    conn.execute("PRAGMA busy_timeout=5000")
                    conn.execute("PRAGMA foreign_keys=ON")
                except sqlite3.Error:
                    pass
                conn.row_factory = sqlite3.Row

                # 测试连接是否可用
                conn.execute("SELECT 1")

                cursor = conn.cursor()
                self._conn = conn
                self._cursor = cursor

                # 增加连接计数
                _increment_connection_counter()

                return conn, cursor

            except sqlite3.OperationalError as e:
                last_error = e
                locked = 'locked' in str(e).lower()
                if locked and attempt < self._max_retries - 1:
                    # 指数退避：0.1s, 0.2s, 0.4s
                    wait_time = 0.1 * (2 ** attempt)
                    print(f"数据库锁定，{wait_time}秒后重试 "
                          f"(尝试 {attempt + 1}/{self._max_retries})")
                    time.sleep(wait_time)
                    if conn is not None:
                        conn.close()
                    continue
                if conn is not None:
                    conn.close()
                raise
            except (sqlite3.Error, OSError, ValueError):
                # 其他数据库或系统异常直接抛出
                if conn is not None:
                    conn.close()
                raise

        # 所有重试都失败
        raise last_error if last_error else sqlite3.OperationalError(
            "无法获取数据库连接"
        )

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._conn is not None:
            self._conn.close()
            # 减少连接计数
            _decrement_connection_counter()


class PooledDBConnection:
    """连接池上下文管理器（带重试机制）"""

    def __init__(self, max_retries=3):
        self._conn: Optional[sqlite3.Connection] = None
        self._cursor: Optional[sqlite3.Cursor] = None
        self._max_retries = max_retries

    def __enter__(self) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
        # 从池中获取连接（带重试）
        self._conn = _get_connection_with_retry(self._max_retries)
        self._cursor = self._conn.cursor()

        # 增加连接计数
        _increment_connection_counter()

        return self._conn, self._cursor

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._conn is not None:
            # 减少连接计数
            _decrement_connection_counter()

            # 将连接返回池中
            _return_connection_to_pool(self._conn)

            self._conn = None
            self._cursor = None


@handle_database_error
def get_db_connection() -> DBConnection:
    """返回一个可用于 with 语句的数据库连接管理器"""
    db_path = os.path.join(os.path.dirname(__file__), "pricing_system.db")
    return DBConnection(db_path)


def get_pooled_db_connection() -> PooledDBConnection:
    """返回一个使用连接池的数据库连接管理器"""
    return PooledDBConnection()


def get_enhanced_db_connection():
    """
    获取增强的数据库连接（推荐使用）
    提供连接泄露检测和自动修复功能
    """
    try:
        from .enhanced_connection_manager import get_enhanced_db_connection
        return get_enhanced_db_connection()
    except ImportError:
        # 如果增强连接管理器不可用，回退到标准连接
        print("警告: 增强连接管理器不可用，使用标准连接")
        return get_pooled_db_connection()


def get_enhanced_connection_stats():
    """获取增强连接池统计信息"""
    try:
        from .enhanced_connection_manager import (
            get_connection_stats as enhanced_stats
        )
        return enhanced_stats()
    except ImportError:
        # 如果增强连接管理器不可用，回退到标准连接统计
        # 调用模块级别的 get_connection_stats 函数
        return get_connection_stats()


def current_user_id():
    """获取当前用户ID"""
    return st.session_state.user["id"]


def is_admin():
    """检查当前用户是否为管理员"""
    if not hasattr(st.session_state, 'user') or st.session_state.user is None:
        return False
    return st.session_state.user.get('role') == 'admin'


def require_admin():
    """要求管理员权限，否则抛出异常"""
    if not is_admin():
        raise PermissionError("此操作需要管理员权限")


def get_system_config(
        config_key: str, default_value: Optional[str] = None
) -> Optional[str]:
    """获取系统配置值"""
    with get_db_connection() as (conn, c):
        result = c.execute(
            "SELECT config_value FROM system_config WHERE config_key = ?",
            (config_key,)
        ).fetchone()
        return result[0] if result else default_value


def set_system_config(
        config_key: str, config_value: str, description: Optional[str] = None
) -> bool:
    """设置系统配置值"""
    with get_db_connection() as (conn, c):
        try:
            c.execute("""
                INSERT OR REPLACE INTO system_config
                (config_key, config_value, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (config_key, config_value, description or ''))
            conn.commit()
            return True
        except Exception as e:
            print(f"设置系统配置失败: {e}")
            return False


def is_registration_open() -> bool:
    """检查是否开放注册"""
    config_value = get_system_config('open_registration', 'false')
    return config_value is not None and config_value.lower() == 'true'

# 数据库升级相关函数


def _upgrade_logistics_battery():
    """升级物流表电池相关字段"""
    with get_db_connection() as (conn, c):
        c.execute("PRAGMA table_info(logistics)")
        cols = [col[1] for col in c.fetchall()]
        if "battery_capacity_limit_wh" not in cols:
            c.execute(
                "ALTER TABLE logistics ADD COLUMN "
                "battery_capacity_limit_wh REAL"
            )
        if "require_msds" not in cols:
            c.execute(
                "ALTER TABLE logistics ADD COLUMN "
                "require_msds INTEGER DEFAULT 0"
            )
        conn.commit()


def _upgrade_logistics_volume_coefficient():
    """升级物流表体积系数字段"""
    with get_db_connection() as (conn, c):
        c.execute("PRAGMA table_info(logistics)")
        cols = [col[1] for col in c.fetchall()]
        if "volume_coefficient" not in cols:
            c.execute(
                "ALTER TABLE logistics ADD COLUMN "
                "volume_coefficient REAL DEFAULT 5000"
            )
        conn.commit()


def _upgrade_max_size_to_sides(table: str):
    """升级旧表结构：max_size -> max_sum_of_sides + max_longest_side"""
    with get_db_connection() as (conn, c):
        # 1. 检查是否已有新字段
        c.execute(f"PRAGMA table_info({table})")
        cols = [col[1] for col in c.fetchall()]
        if "max_sum_of_sides" in cols and "max_longest_side" in cols:
            return  # 已升级过
        # 2. 重命名旧表
        c.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
        # 3. 创建包含所有字段的新表
        c.execute(
            """
            CREATE TABLE logistics (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT,
                type TEXT,
                min_days INTEGER,
                max_days INTEGER,
                price_limit REAL,
                base_fee REAL,
                weight_factor REAL,
                min_weight INTEGER,
                max_weight INTEGER,
                max_sum_of_sides INTEGER,
                max_longest_side INTEGER,
                volume_mode TEXT
                    CHECK(volume_mode IN ('none',
                                          'max_actual_vs_volume',
                                          'longest_side'))
                    DEFAULT 'none',
                longest_side_threshold INTEGER DEFAULT 0,
                volume_coefficient REAL DEFAULT 5000,
                allow_battery INTEGER,
                allow_flammable INTEGER
            )
            """
        )
        # 4. 迁移旧数据
        c.execute(
            """
            INSERT INTO logistics (
                user_id, name, type, min_days, max_days, price_limit,
                base_fee, weight_factor,
                min_weight, max_weight,
                max_sum_of_sides, max_longest_side,
                volume_mode, longest_side_threshold,
                volume_coefficient, allow_battery, allow_flammable
            )
            SELECT
                user_id, name, type, min_days, max_days, price_limit,
                base_fee, weight_factor,
                min_weight, max_weight,
                COALESCE(max_size, 0), COALESCE(max_size, 0),
                volume_mode, longest_side_threshold,
                5000, allow_battery, allow_flammable
            FROM logistics_old
            """
        )
        # 5. 清理旧表
        c.execute(f"DROP TABLE {table}_old")
        conn.commit()


def _upgrade_table_user_id(table: str):
    """给旧表加 user_id 字段（如存在）"""
    with get_db_connection() as (conn, c):
        cols = [col[1]
                for col in c.execute(f"PRAGMA table_info({table})").fetchall()]
        if "user_id" in cols:
            return
        c.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
        if table == "logistics":
            c.execute(
                """
                CREATE TABLE logistics (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT,
                    type TEXT,
                    min_days INTEGER,
                    max_days INTEGER,
                    price_limit REAL,
                    base_fee REAL,
                    weight_factor REAL,
                    min_weight INTEGER,
                    max_weight INTEGER,
                    max_sum_of_sides INTEGER,
                    max_longest_side INTEGER,
                    volume_mode TEXT DEFAULT 'none',
                    longest_side_threshold INTEGER DEFAULT 0,
                    volume_coefficient REAL DEFAULT 5000,
                    allow_battery INTEGER,
                    allow_flammable INTEGER
                )
                """
            )
            c.execute(
                """
                INSERT INTO logistics (
                    user_id, name, type, min_days, max_days, price_limit,
                    base_fee, weight_factor,
                    min_weight, max_weight,
                    max_sum_of_sides, max_longest_side,
                    volume_mode, longest_side_threshold,
                    volume_coefficient, allow_battery, allow_flammable
                )
                SELECT
                    (SELECT id FROM users WHERE role='admin' LIMIT 1),
                    name, type, min_days, max_days, price_limit,
                    base_fee, weight_factor,
                    min_weight, max_weight,
                    COALESCE(max_size, 0), COALESCE(max_size, 0),
                    volume_mode, longest_side_threshold,
                    5000, allow_battery, allow_flammable
                FROM logistics_old
                """
            )
        elif table == "products":
            c.execute(
                """
                CREATE TABLE products (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT,
                    russian_name TEXT,
                    category TEXT,
                    model TEXT,
                    unit_price REAL,
                    weight_g INTEGER,
                    length_cm INTEGER,
                    width_cm INTEGER,
                    height_cm INTEGER,
                    is_cylinder INTEGER,
                    cylinder_diameter REAL,
                    cylinder_length REAL,
                    has_battery INTEGER,
                    battery_capacity_wh REAL,
                    battery_capacity_mah INTEGER,
                    battery_voltage REAL,
                    has_msds INTEGER,
                    has_flammable INTEGER,
                    shipping_fee REAL,
                    labeling_fee REAL
                )
                """
            )
            c.execute(
                """
                INSERT INTO products (
                    user_id, name, russian_name, category, model,
                    unit_price, weight_g, length_cm, width_cm, height_cm,
                    is_cylinder, cylinder_diameter, cylinder_length,
                    has_battery, battery_capacity_wh, battery_capacity_mah,
                    battery_voltage, has_msds, has_flammable,
                    shipping_fee, labeling_fee
                )
                SELECT
                    (SELECT id FROM users WHERE role='admin' LIMIT 1),
                    name, russian_name, category, model,
                    unit_price, weight_g, length_cm, width_cm, height_cm,
                    is_cylinder, cylinder_diameter, 0.0,
                    has_battery, battery_capacity_wh, battery_capacity_mah,
                    battery_voltage, has_msds, has_flammable,
                    shipping_fee, labeling_fee
                FROM products_old
                """
            )
        c.execute(f"DROP TABLE {table}_old")
        conn.commit()


def _upgrade_old_volume_battery():
    """升级旧表体积和电池因子字段"""
    _upgrade_logistics_volume_coefficient()
    with get_db_connection() as (conn, c):
        cols = [col[1] for col in c.execute(
            "PRAGMA table_info(logistics)").fetchall()]
        # 如果旧表里还有 volume_factor / battery_factor 就 DROP COLUMN
        # SQLite ≥ 3.35 支持 DROP COLUMN；低版本需重建表
        for col in ["volume_factor", "battery_factor"]:
            if col in cols:
                c.execute(f"ALTER TABLE logistics DROP COLUMN {col}")
        conn.commit()


def _upgrade_logistics_new_fields():
    """升级：新增重量计费字段、电池容量限制字段"""
    with get_db_connection() as (conn, c):
        cols = [col[1] for col in c.execute(
            "PRAGMA table_info(logistics)").fetchall()]
        new_cols = {
            "battery_capacity_limit_wh": "REAL DEFAULT 0",
            "require_msds": "INTEGER DEFAULT 0",
            "fee_mode": "TEXT DEFAULT 'base_plus_continue'",
            "first_fee": "REAL DEFAULT 0",
            "first_weight_g": "INTEGER DEFAULT 0",
            "continue_fee": "REAL DEFAULT 0",
            "continue_unit": "TEXT DEFAULT '100'",
            "volume_coefficient": "INTEGER DEFAULT 5000",
            "price_limit_rub": "REAL DEFAULT 0",
            "price_min_rub": "REAL DEFAULT 0",
            "max_second_side": "INTEGER DEFAULT 0",
            "min_second_side": "INTEGER DEFAULT 0",
            "min_length": "INTEGER DEFAULT 0",
            "max_cylinder_sum": "INTEGER DEFAULT 0",
            "min_cylinder_sum": "INTEGER DEFAULT 0",
            "max_cylinder_length": "INTEGER DEFAULT 0",
            "min_cylinder_length": "INTEGER DEFAULT 0",
            "allow_battery": "INTEGER DEFAULT 0",
            "allow_flammable": "INTEGER DEFAULT 0",
            "delivery_method": "TEXT DEFAULT 'unknown'",
            "priority_group": "TEXT DEFAULT 'D'",
            "price_limit_currency": "TEXT DEFAULT 'RUB'",
            "price_min_currency": "TEXT DEFAULT 'RUB'",
        }
        for col, def_sql in new_cols.items():
            if col not in cols:
                c.execute(f"ALTER TABLE logistics ADD COLUMN {col} {def_sql}")
        conn.commit()


def _upgrade_products_cylinder_length():
    """升级：新增产品圆柱长度字段"""
    with get_db_connection() as (conn, c):
        cols = [col[1]
                for col in c.execute("PRAGMA table_info(products)").fetchall()]
        if "cylinder_length" not in cols:
            c.execute(
                "ALTER TABLE products ADD COLUMN cylinder_length "
                "REAL DEFAULT 0"
            )
        conn.commit()


def _upgrade_products_new_fields():
    """升级：新增产品定价相关字段"""
    with get_db_connection() as (conn, c):
        cols = [col[1]
                for col in c.execute("PRAGMA table_info(products)").fetchall()]
        new_cols = {
            "promotion_discount": "REAL DEFAULT 0.05",
            "promotion_cost_rate": "REAL DEFAULT 0.115",
            "target_profit_margin": "REAL DEFAULT 0.5",
            "commission_rate": "REAL DEFAULT 0.17",
            "withdrawal_fee_rate": "REAL DEFAULT 0.01",
            "payment_processing_fee": "REAL DEFAULT 0.01"
        }
        for col, def_sql in new_cols.items():
            if col not in cols:
                c.execute(f"ALTER TABLE products ADD COLUMN {col} {def_sql}")
        conn.commit()


def _upgrade_users_subscription_fields():
    """升级：新增用户订阅相关字段"""
    with get_db_connection() as (conn, c):
        cols = [col[1]
                for col in c.execute("PRAGMA table_info(users)").fetchall()]
        new_cols = {
            "user_type": "TEXT DEFAULT 'permanent'",
            "expiry_date": "TEXT",
            "remaining_calculations": "INTEGER DEFAULT -1",
            "first_login_date": "TEXT",
            "test_days_remaining": "INTEGER DEFAULT 0",
            "subscription_type": "TEXT DEFAULT 'free'",
            "subscription_expires": "INTEGER",
            "efficiency_promo_used": "INTEGER DEFAULT 0",  # 记录是否使用过效率版首月1元优惠
            "created_at": "TEXT DEFAULT ''",  # 注册时间
            "last_login": "TEXT"  # 最后登录时间
        }
        for col, def_sql in new_cols.items():
            if col not in cols:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {def_sql}")
        conn.commit()


def _upgrade_users_test_flag():
    """升级：新增用户测试标记字段"""
    with get_db_connection() as (conn, c):
        cols = [col[1]
                for col in c.execute("PRAGMA table_info(users)").fetchall()]
        if "is_test_user" not in cols:
            c.execute(
                "ALTER TABLE users ADD COLUMN is_test_user "
                "INTEGER DEFAULT 0"
            )
        conn.commit()


def _upgrade_performance_indexes():
    """升级：添加复合索引优化查询性能"""
    with get_db_connection() as (conn, c):
        # 检查索引是否已存在
        existing_indexes = c.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        existing_index_names = [idx[0] for idx in existing_indexes]

        # 1. payment_orders表 - 用户+状态复合索引（支付历史查询）
        if "idx_payment_orders_user_status" not in existing_index_names:
            c.execute("""
                CREATE INDEX idx_payment_orders_user_status
                ON payment_orders(user_id, status)
            """)

        # 2. user_login_log表 - 用户+时间复合索引（活跃度统计）
        if "idx_user_login_log_user_time" not in existing_index_names:
            c.execute("""
                CREATE INDEX idx_user_login_log_user_time
                ON user_login_log(user_id, login_time DESC)
            """)

        # 3. user_behavior_log表 - 用户+类型复合索引（行为分析）
        if "idx_user_behavior_log_user_type" not in existing_index_names:
            c.execute("""
                CREATE INDEX idx_user_behavior_log_user_type
                ON user_behavior_log(user_id, behavior_type)
            """)

        # 4. payment_orders表 - 创建时间+状态索引（收入统计）
        if "idx_payment_orders_time_status" not in existing_index_names:
            c.execute("""
                CREATE INDEX idx_payment_orders_time_status
                ON payment_orders(created_at DESC, status)
            """)

        # 5. products表 - 用户+名称索引（产品搜索）
        if "idx_products_user_name" not in existing_index_names:
            c.execute("""
                CREATE INDEX idx_products_user_name
                ON products(user_id, name)
            """)

        conn.commit()


def _upgrade_logistics_price_min():
    """升级：新增物流价格下限字段"""
    with get_db_connection() as (conn, c):
        cols = [col[1] for col in c.execute(
            "PRAGMA table_info(logistics)").fetchall()]
        if "price_min" not in cols:
            c.execute(
                "ALTER TABLE logistics ADD COLUMN price_min REAL DEFAULT 0"
            )
        conn.commit()


def _upgrade_products_return_rate():
    """升级：新增产品历史退货率字段"""
    with get_db_connection() as (conn, c):
        cols = [col[1] for col in c.execute(
            "PRAGMA table_info(products)").fetchall()]
        if "return_rate" not in cols:
            c.execute(
                "ALTER TABLE products ADD COLUMN return_rate REAL DEFAULT 0"
            )
        conn.commit()


def _upgrade_products_vat_rate():
    """升级：新增产品增值税率字段"""
    with get_db_connection() as (conn, c):
        cols = [col[1] for col in c.execute(
            "PRAGMA table_info(products)").fetchall()]
        if "vat_rate" not in cols:
            c.execute(
                "ALTER TABLE products ADD COLUMN vat_rate REAL DEFAULT 0"
            )
        conn.commit()


def _upgrade_payment_orders_duration():
    """升级：新增支付订单时长字段"""
    with get_db_connection() as (conn, c):
        cols = [col[1] for col in c.execute(
            "PRAGMA table_info(payment_orders)").fetchall()]
        if "duration" not in cols:
            c.execute(
                "ALTER TABLE payment_orders ADD COLUMN duration TEXT"
            )
        conn.commit()


def _upgrade_subscription_upgrade_system():
    """升级：添加订阅升级系统相关字段和表"""
    with get_db_connection() as (conn, c):
        # 1. 添加 users 表的升级相关字段
        cols = [col[1] for col in c.execute(
            "PRAGMA table_info(users)").fetchall()]

        new_fields = {
            'billing_cycle': 'TEXT DEFAULT "month"',
            'last_paid_amount': 'REAL DEFAULT 0',
            'subscription_start': 'INTEGER',
        }

        for field_name, field_def in new_fields.items():
            if field_name not in cols:
                sql = f"ALTER TABLE users ADD COLUMN {field_name} {field_def}"
                c.execute(sql)

        # 2. 添加 payment_orders 表的升级相关字段
        payment_cols = [col[1] for col in c.execute(
            "PRAGMA table_info(payment_orders)").fetchall()]

        payment_new_fields = {
            'is_upgrade': 'INTEGER DEFAULT 0',
            'upgrade_from_plan': 'TEXT',
            'upgrade_to_plan': 'TEXT',
            'remaining_value': 'REAL DEFAULT 0',
        }

        for field_name, field_def in payment_new_fields.items():
            if field_name not in payment_cols:
                sql = (
                    f"ALTER TABLE payment_orders ADD COLUMN "
                    f"{field_name} {field_def}"
                )
                c.execute(sql)

        # 3. 创建升级历史表
        c.execute("""
            CREATE TABLE IF NOT EXISTS subscription_upgrade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                from_plan TEXT NOT NULL,
                to_plan TEXT NOT NULL,
                from_cycle TEXT,
                to_cycle TEXT,
                upgrade_time INTEGER NOT NULL,
                remaining_value REAL DEFAULT 0,
                difference_paid REAL DEFAULT 0,
                target_price REAL NOT NULL,
                payment_order_id TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.commit()


def _upgrade_statistics_tables():
    """升级：添加统计与运营看板相关表"""
    with get_db_connection() as (conn, c):
        # 1. 创建用户登录日志表
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_login_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                login_time INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                device_type TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # 为登录日志创建索引以提升查询性能
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_login_log_user_id
            ON user_login_log(user_id)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_login_log_login_time
            ON user_login_log(login_time)
        """)

        # 2. 创建管理员操作日志表（增强版）
        c.execute("""
            CREATE TABLE IF NOT EXISTS admin_action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                action_detail TEXT,
                target_user_id INTEGER,
                target_type TEXT,
                ip_address TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (admin_id) REFERENCES users(id),
                FOREIGN KEY (target_user_id) REFERENCES users(id)
            )
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_action_log_admin_id
            ON admin_action_log(admin_id)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_admin_action_log_created_at
            ON admin_action_log(created_at)
        """)

        # 3. 创建异常告警记录表
        c.execute("""
            CREATE TABLE IF NOT EXISTS alert_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                alert_level TEXT NOT NULL,
                description TEXT NOT NULL,
                threshold_value REAL,
                actual_value REAL,
                status TEXT DEFAULT 'unhandled',
                handled_by INTEGER,
                handled_at INTEGER,
                handle_note TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (handled_by) REFERENCES users(id)
            )
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_records_created_at
            ON alert_records(created_at)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_records_status
            ON alert_records(status)
        """)

        # 4. 创建统计数据缓存表
        c.execute("""
            CREATE TABLE IF NOT EXISTS statistics_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE NOT NULL,
                cache_data TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_statistics_cache_key
            ON statistics_cache(cache_key)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_statistics_cache_expires_at
            ON statistics_cache(expires_at)
        """)

        # 5. 创建用户行为记录表（新增）
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_behavior_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                behavior_type TEXT NOT NULL,
                behavior_detail TEXT,
                calculation_mode TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_behavior_user_id
            ON user_behavior_log(user_id)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_behavior_type
            ON user_behavior_log(behavior_type)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_behavior_created_at
            ON user_behavior_log(created_at)
        """)

        # 6. 创建预警配置表（新增）
        c.execute("""
            CREATE TABLE IF NOT EXISTS alert_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                threshold_value REAL,
                comparison_type TEXT,
                is_enabled INTEGER DEFAULT 1,
                notification_method TEXT DEFAULT 'system',
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)

        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_config_metric_name
            ON alert_config(metric_name)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_config_is_enabled
            ON alert_config(is_enabled)
        """)

        # 7. 为payment_orders表添加order_type字段（如果不存在）
        try:
            c.execute("""
                SELECT order_type FROM payment_orders LIMIT 1
            """)
        except sqlite3.OperationalError:
            # 字段不存在，添加它
            c.execute("""
                ALTER TABLE payment_orders
                ADD COLUMN order_type TEXT DEFAULT NULL
            """)
            # 创建索引
            c.execute("""
                CREATE INDEX IF NOT EXISTS idx_payment_orders_order_type
                ON payment_orders(order_type)
            """)

        # 8. 创建套餐配置表（新增）
        c.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_code TEXT UNIQUE NOT NULL,
                plan_name TEXT NOT NULL,
                display_price_month REAL NOT NULL,
                display_price_year REAL NOT NULL,
                actual_price_month REAL NOT NULL,
                actual_price_year REAL NOT NULL,
                test_price_month REAL NOT NULL DEFAULT 0,
                test_price_year REAL NOT NULL DEFAULT 0,
                calc_limit INTEGER NOT NULL DEFAULT -1,
                logistics_limit INTEGER NOT NULL DEFAULT 1,
                description TEXT,
                features TEXT,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)

        # 为plans表创建索引
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_plans_code
            ON plans(plan_code)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_plans_active
            ON plans(is_active)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_plans_sort_order
            ON plans(sort_order)
        """)

        # 9. 初始化默认套餐数据（如果表为空）
        count = c.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
        if count == 0:
            # 免费版
            c.execute("""
                INSERT INTO plans (
                    plan_code, plan_name,
                    display_price_month, display_price_year,
                    actual_price_month, actual_price_year,
                    test_price_month, test_price_year,
                    calc_limit, logistics_limit,
                    description, features, sort_order
                ) VALUES (
                    'free', '免费版',
                    0, 0,
                    0, 0,
                    0, 0,
                    10, 1,
                    '适合初次体验的用户',
                    '每日10次计算|1个物流模板|基础功能',
                    1
                )
            """)

            # 效率版
            c.execute("""
                INSERT INTO plans (
                    plan_code, plan_name,
                    display_price_month, display_price_year,
                    actual_price_month, actual_price_year,
                    test_price_month, test_price_year,
                    calc_limit, logistics_limit,
                    description, features, sort_order
                ) VALUES (
                    'efficiency', '效率版',
                    9.9, 99,
                    9.9, 99,
                    1.1, 1.2,
                    500, 3,
                    '适合中小规模卖家',
                    '每月500次计算|3个物流模板|优先客服',
                    2
                )
            """)

            # 专业版
            c.execute("""
                INSERT INTO plans (
                    plan_code, plan_name,
                    display_price_month, display_price_year,
                    actual_price_month, actual_price_year,
                    test_price_month, test_price_year,
                    calc_limit, logistics_limit,
                    description, features, sort_order
                ) VALUES (
                    'professional', '专业版',
                    149, 1499,
                    149, 1499,
                    1.3, 1.4,
                    -1, 10,
                    '适合大规模专业卖家',
                    '无限次计算|10个物流模板|专属客服|数据导出',
                    3
                )
            """)

            # 企业版
            c.execute("""
                INSERT INTO plans (
                    plan_code, plan_name,
                    display_price_month, display_price_year,
                    actual_price_month, actual_price_year,
                    test_price_month, test_price_year,
                    calc_limit, logistics_limit,
                    description, features, sort_order
                ) VALUES (
                    'enterprise', '企业版',
                    299, 2988,
                    299, 2988,
                    1.5, 1.6,
                    -1, -1,
                    '适合企业团队使用',
                    '无限次计算|无限物流模板|API接口|定制开发|7x24服务',
                    4
                )
            """)

        conn.commit()


def create_user(username, password, role="user", email=None,
                user_type="free", is_test_user=False):
    """创建用户，返回user_id或None

    Args:
        username: 用户名
        password: 密码
        role: 角色 (user/admin)
        email: 邮箱 (可选)
        user_type: 用户类型 (free/efficiency/professional/enterprise)
        is_test_user: 是否为测试用户，测试用户会在测试结束后自动清理
    """
    # 确保数据库已初始化
    init_db()

    # 验证用户名
    if not username or len(username.strip()) == 0:
        return None

    # 验证密码强度
    password_validation = validate_password_strength(password)
    if not password_validation['is_valid']:
        return None

    with get_db_connection() as (conn, c):

        # 检查用户名是否已存在（不区分大小写）
        existing_user = c.execute(
            "SELECT username FROM users WHERE LOWER(username) = LOWER(?)",
            (username,)
        ).fetchone()

        if existing_user:
            return None  # 用户名已存在

        # 检查邮箱是否已存在（如果提供了邮箱）
        if email:
            existing_email = c.execute(
                "SELECT email FROM users WHERE LOWER(email) = LOWER(?)",
                (email,)
            ).fetchone()

            if existing_email:
                return None  # 邮箱已存在

        # 使用bcrypt加盐哈希密码
        hashed_password = hash_password(password)

        # 根据用户类型设置计算次数
        if user_type == "free":
            remaining_calculations = 10
        elif user_type in [
            "test", "gratitude", "efficiency", "professional", "enterprise"
        ]:
            remaining_calculations = -1  # 无限次
        else:
            remaining_calculations = 10  # 默认为免费版

        try:
            # 设置注册时间为当前时间
            from datetime import datetime
            created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 转换is_test_user为整数
            is_test = 1 if is_test_user else 0

            if email:
                c.execute(
                    "INSERT INTO users (username, password, role, email, "
                    "user_type, subscription_type, "
                    "remaining_calculations, "
                    "created_at, is_test_user) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (username, hashed_password, role, email, user_type,
                     user_type, remaining_calculations, created_at, is_test),
                )
            else:
                c.execute(
                    "INSERT INTO users (username, password, role, "
                    "user_type, subscription_type, "
                    "remaining_calculations, "
                    "created_at, is_test_user) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (username, hashed_password, role, user_type, user_type,
                     remaining_calculations, created_at, is_test),
                )
            conn.commit()
            # 返回新创建用户的ID
            user_id = c.lastrowid
            return user_id
        except sqlite3.IntegrityError:
            return None


def verify_user(identifier, password):
    """验证用户"""
    # 确保数据库已初始化
    init_db()
    with get_db_connection() as (conn, c):

        # 首先根据用户名或邮箱查找用户（用户名不区分大小写）
        user = c.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?) " +
            "OR LOWER(email) = LOWER(?)",
            (identifier, identifier),
        ).fetchone()

        if user:
            stored_password = user[2]  # 存储的密码哈希

            # 使用新的密码验证函数（支持bcrypt和旧SHA256格式）
            if verify_password(password, stored_password):
                # 如果是旧格式密码，自动升级到bcrypt
                if not is_bcrypt_hash(stored_password):
                    upgrade_user_password_to_bcrypt(user[0], password)

                return {
                    'id': user[0],
                    'username': user[1],
                    'password': user[2],
                    'role': user[3],
                    'email': user[4]
                }

        return None


def upgrade_user_password_to_bcrypt(user_id, password):
    """
    将用户密码从SHA256格式升级到bcrypt格式

    Args:
        user_id (int): 用户ID
        password (str): 明文密码
    """
    with get_db_connection() as (conn, c):
        new_hashed_password = hash_password(password)

        c.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (new_hashed_password, user_id)
        )
        conn.commit()


def init_db():
    """初始化数据库"""
    with get_db_connection() as (conn, c):
        # 1. 三张基础表：users / products / logistics
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT,
                email TEXT UNIQUE,
                preferred_mode TEXT DEFAULT 'fast'
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT,
                russian_name TEXT,
                category TEXT,
                model TEXT,
                unit_price REAL,
                weight_g INTEGER,
                length_cm INTEGER,
                width_cm INTEGER,
                height_cm INTEGER,
                is_cylinder INTEGER,
                cylinder_diameter REAL,
                cylinder_length REAL,
                has_battery INTEGER,
                battery_capacity_wh REAL,
                battery_capacity_mah INTEGER,
                battery_voltage REAL,
                has_msds INTEGER,
                has_flammable INTEGER,
                shipping_fee REAL,
                labeling_fee REAL,
                promotion_discount     REAL DEFAULT 0.05,
                promotion_cost_rate    REAL DEFAULT 0.115,
                target_profit_margin   REAL DEFAULT 0.5,
                commission_rate        REAL DEFAULT 0.17,
                withdrawal_fee_rate    REAL DEFAULT 0.01,
                payment_processing_fee REAL DEFAULT 0.01,
                return_rate            REAL DEFAULT 0,
                vat_rate               REAL DEFAULT 0
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS logistics (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT,
                type TEXT,
                min_days INTEGER,
                max_days INTEGER,
                price_limit REAL,
                price_limit_rub REAL,
                price_min REAL DEFAULT 0,
                price_min_rub REAL DEFAULT 0,
                base_fee REAL DEFAULT 0,
                min_weight INTEGER,
                max_weight INTEGER,
                max_sum_of_sides INTEGER,
                max_longest_side INTEGER,
                max_second_side INTEGER DEFAULT 0,
                min_second_side INTEGER DEFAULT 0,
                min_length INTEGER DEFAULT 0,
                max_cylinder_sum INTEGER DEFAULT 0,
                min_cylinder_sum INTEGER DEFAULT 0,
                max_cylinder_length INTEGER DEFAULT 0,
                min_cylinder_length INTEGER DEFAULT 0,
                volume_mode TEXT
                    CHECK(
                        volume_mode IN (
                            'none',
                            'max_actual_vs_volume',
                            'longest_side'
                        )
                    )
                    DEFAULT 'none',
                longest_side_threshold INTEGER DEFAULT 0,
                allow_battery INTEGER,
                allow_flammable INTEGER,
                battery_capacity_limit_wh REAL DEFAULT 0,
                require_msds INTEGER DEFAULT 0,
                fee_mode TEXT DEFAULT 'base_plus_continue',
                first_fee REAL DEFAULT 0,
                first_weight_g INTEGER DEFAULT 0,
                continue_fee REAL DEFAULT 0,
                continue_unit TEXT DEFAULT '100',
                volume_coefficient REAL DEFAULT 5000,
                delivery_method TEXT DEFAULT 'unknown',
                priority_group TEXT DEFAULT 'D',
                price_limit_currency TEXT DEFAULT 'RUB',
                price_min_currency TEXT DEFAULT 'RUB'
            )
            """
        )

        # 创建系统配置表
        c.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建支付订单表
        c.execute("""
            CREATE TABLE IF NOT EXISTS payment_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT NOT NULL,
                duration TEXT,
                status TEXT DEFAULT 'PENDING',
                wechat_transaction_id TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # 初始化系统配置
        c.execute("""
            INSERT OR IGNORE INTO system_config
            (config_key, config_value, description)
            VALUES ('open_registration', 'false', '是否开放用户注册')
        """)
        conn.commit()
        # 2. 升级旧表（只跑一次）
        _upgrade_table_user_id("products")
        _upgrade_table_user_id("logistics")
        _upgrade_max_size_to_sides("logistics")
        _upgrade_old_volume_battery()
        _upgrade_logistics_new_fields()
        _upgrade_products_cylinder_length()
        _upgrade_products_new_fields()
        _upgrade_logistics_price_min()
        _upgrade_products_return_rate()
        _upgrade_products_vat_rate()
        _upgrade_users_subscription_fields()
        _upgrade_users_test_flag()
        _upgrade_payment_orders_duration()
        _upgrade_subscription_upgrade_system()
        _upgrade_statistics_tables()
        _upgrade_performance_indexes()
        # 3. 初始管理员（避免递归调用）
        admin_user = c.execute(
            "SELECT * FROM users WHERE username = ?",
            ("admin",)
        ).fetchone()
        if not admin_user:
            # 使用bcrypt为默认管理员密码加盐哈希
            hashed_password = hash_password("admin123")
            c.execute(
                (
                    "INSERT INTO users (username, password, role, email, "
                    "user_type) VALUES (?, ?, ?, ?, ?)"
                ),
                (
                    "admin",
                    hashed_password,
                    "admin",
                    "admin@example.com",
                    "permanent",
                ),
            )
            conn.commit()

        # 4. 数据保护策略调整：允许管理员手动删除其产品
        # 取消历史触发器，改为通过业务逻辑防止“非手动路径”误删
        try:
            c.execute(
                "DROP TRIGGER IF EXISTS trg_prevent_delete_admin_products"
            )
            conn.commit()
        except sqlite3.Error:
            pass


def add_product(product_data):
    """添加新产品"""
    with get_db_connection() as (conn, c):

        # 提取产品数据
        fields = [
            'user_id', 'name', 'russian_name', 'category', 'model',
            'unit_price', 'weight_g', 'length_cm', 'width_cm', 'height_cm',
            'is_cylinder', 'cylinder_diameter', 'cylinder_length',
            'has_battery',
            'battery_capacity_wh', 'battery_capacity_mah', 'battery_voltage',
            'has_msds', 'has_flammable', 'shipping_fee', 'labeling_fee',
            'promotion_cost_rate',
            'target_profit_margin',
            'commission_rate', 'withdrawal_fee_rate',
            'payment_processing_fee', 'return_rate'
        ]

        # 构建SQL语句
        placeholders = ','.join(['?' for _ in fields])
        field_names = ','.join(fields)

        # 获取值
        values = [product_data.get(field, 0) for field in fields]

        c.execute(
            f"INSERT INTO products ({field_names}) VALUES ({placeholders})",
            values
        )
        conn.commit()
        return c.lastrowid


# @st.cache_resource(ttl=600)  # 缓存10分钟 - 临时禁用
def get_all_products_for_user(user_id):
    """获取用户的所有产品"""
    with get_db_connection() as (conn, c):
        products = c.execute(
            "SELECT * FROM products WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        return [dict(product) for product in products]


def ensure_admin_product_deletion_allowed() -> None:
    """确保不存在阻止删除管理员产品的触发器。

    某些历史环境可能残留触发器，导致手动删除被阻断。
    本函数幂等，若不存在该触发器则忽略。
    """
    with get_db_connection() as (conn, c):
        try:
            c.execute(
                "DROP TRIGGER IF EXISTS trg_prevent_delete_admin_products"
            )
            conn.commit()
        except sqlite3.Error:
            pass


def get_product_by_id(product_id, user_id):
    """根据ID获取产品 - 强制要求用户ID验证"""
    if user_id is None:
        raise ValueError("user_id参数是必需的，以确保数据安全隔离")

    with get_db_connection() as (conn, c):
        product = c.execute(
            "SELECT * FROM products WHERE id = ? AND user_id = ?",
            (product_id, user_id)
        ).fetchone()
        if product:
            # Convert tuple to dict using column names
            columns = [description[0] for description in c.description]
            return dict(zip(columns, product))
        return None


def delete_product(product_id, user_id):
    """删除产品"""
    with get_db_connection() as (conn, c):
        c.execute(
            "DELETE FROM products WHERE id = ? AND user_id = ?",
            (product_id, user_id)
        )
        conn.commit()
        return c.rowcount > 0


def batch_delete_products(product_ids, user_id):
    """批量删除产品"""
    if not product_ids:
        return 0

    with get_db_connection() as (conn, c):
        placeholders = ','.join(['?' for _ in product_ids])
        params = list(product_ids) + [user_id]

        c.execute(
            f"DELETE FROM products WHERE id IN ({placeholders}) "
            f"AND user_id = ?",
            params
        )
        conn.commit()
        return c.rowcount


def update_product(product_id, user_id, updates):
    """更新产品信息"""
    if not updates:
        return False

    with get_db_connection() as (conn, c):

        # 构建UPDATE语句
        set_clauses = []
        values = []
        for field, value in updates.items():
            set_clauses.append(f"{field} = ?")
            values.append(value)

        values.extend([product_id, user_id])

        c.execute(
            f"UPDATE products SET {', '.join(set_clauses)} " +
            "WHERE id = ? AND user_id = ?",
            values
        )
        conn.commit()
        return c.rowcount > 0


def batch_update_pricing_params(product_ids, user_id, pricing_updates):
    """批量更新产品定价参数"""
    if not product_ids or not pricing_updates:
        return 0

    with get_db_connection() as (conn, c):

        # 构建UPDATE语句
        set_clauses = []
        values = []
        for field, value in pricing_updates.items():
            set_clauses.append(f"{field} = ?")
            values.append(value)

        placeholders = ','.join(['?' for _ in product_ids])
        values.extend(list(product_ids))
        values.append(user_id)

        c.execute(
            (
                f"UPDATE products SET {', '.join(set_clauses)} "
                f"WHERE id IN ({placeholders}) AND user_id = ?"
            ),
            values,
        )
        conn.commit()
        return c.rowcount


def calculate_and_update_priority_groups(user_id):
    """计算并更新物流优先级分组 - 支持用户隔离"""
    with get_db_connection() as (conn, c):
        # 获取指定用户的物流数据
        logistics = c.execute(
            (
                "SELECT id, type, min_days, max_days FROM logistics "
                "WHERE user_id = ?"
            ),
            (user_id,),
        ).fetchall()

        # 按类型分组
        land_logistics = [log for log in logistics if log['type'] == 'land']
        air_logistics = [log for log in logistics if log['type'] == 'air']

        def calculate_group_averages(logistics_list):
            """计算物流组的平均值"""
            if not logistics_list:
                return 0, 0, 0

            # 过滤出时效不为0的物流（参与平均值计算）
            valid_logistics = [
                log for log in logistics_list
                if log['min_days'] > 0 and log['max_days'] > 0
            ]

            if not valid_logistics:
                return 0, 0, 0

            # 计算平均最快时效(A)
            min_days_sum = sum(log['min_days'] for log in valid_logistics)
            avg_fastest = min_days_sum / len(valid_logistics)

            # 计算平均最慢时效(B)
            max_days_sum = sum(log['max_days'] for log in valid_logistics)
            avg_slowest = max_days_sum / len(valid_logistics)

            # 计算每个物流的平均时效(C)的平均值(D)
            avg_times = []
            for log in valid_logistics:
                avg_time = (log['min_days'] + log['max_days']) / 2
                avg_times.append(avg_time)
            avg_overall = sum(avg_times) / len(avg_times)

            return avg_fastest, avg_slowest, avg_overall

        def assign_priority_group(log, avg_fastest, avg_slowest, avg_overall):
            """为单个物流分配优先级组"""
            min_days = log['min_days']
            max_days = log['max_days']

            # 如果时效为0，分配为E组（优先级最低）
            if min_days == 0 and max_days == 0:
                return 'E'

            avg_time = (min_days + max_days) / 2

            # 计算有多少个值小于平均值
            count_below_avg = 0
            if min_days < avg_fastest:
                count_below_avg += 1
            if max_days < avg_slowest:
                count_below_avg += 1
            if avg_time < avg_overall:
                count_below_avg += 1

            # 根据数量分配组别
            if count_below_avg == 3:
                return 'A'
            elif count_below_avg == 2:
                return 'B'
            elif count_below_avg == 1:
                return 'C'
            else:
                return 'D'

        # 计算陆运组平均值
        land_avg_fastest, land_avg_slowest, land_avg_overall = (
            calculate_group_averages(land_logistics)
        )

        # 计算空运组平均值
        air_avg_fastest, air_avg_slowest, air_avg_overall = (
            calculate_group_averages(air_logistics)
        )

        # 更新陆运物流的优先级组
        for log in land_logistics:
            group = assign_priority_group(
                log, land_avg_fastest, land_avg_slowest, land_avg_overall
            )
            c.execute(
                "UPDATE logistics SET priority_group = ? WHERE id = ?",
                (group, log['id'])
            )

        # 更新空运物流的优先级组
        for log in air_logistics:
            group = assign_priority_group(
                log, air_avg_fastest, air_avg_slowest, air_avg_overall
            )
            c.execute(
                "UPDATE logistics SET priority_group = ? WHERE id = ?",
                (group, log['id'])
            )

        conn.commit()


# @st.cache_resource(ttl=300)  # 缓存5分钟 - 临时禁用
def get_user_subscription_info(user_id):
    """获取用户订阅信息"""
    with get_db_connection() as (conn, c):
        user = c.execute(
            "SELECT id, username, user_type, expiry_date, "
            "remaining_calculations, first_login_date, "
            "test_days_remaining, role, subscription_type, "
            "subscription_expires "
            "FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if user:
            return dict(user)
        return None


def update_user_subscription(user_id, updates):
    """更新用户订阅信息"""
    with get_db_connection() as (conn, c):
        set_clauses = []
        values = []
        for field, value in updates.items():
            set_clauses.append(f"{field} = ?")
            values.append(value)

        values.append(user_id)

        c.execute(
            f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?",
            values
        )
        conn.commit()
        return c.rowcount > 0


# @st.cache_resource(ttl=300)  # 缓存5分钟 - 临时禁用
def check_user_subscription_status(user_id):
    """检查用户订阅状态"""
    from datetime import datetime, date

    user_info = get_user_subscription_info(user_id)
    if not user_info:
        return {'valid': False, 'message': '用户不存在'}

    # 检查用户角色，如果是admin用户，直接返回管理员状态
    user_role = user_info.get('role', 'user')
    if user_role == 'admin':
        return {
            'valid': True,
            'message': '管理员用户',
            'user_type': 'admin',
            'role': 'admin',
        }

    # 优先使用subscription_type字段，如果没有则使用user_type
    user_type = (user_info.get('subscription_type') or
                 user_info.get('user_type', 'permanent'))

    # 永久用户
    if user_type == 'permanent':
        return {'valid': True, 'message': '永久用户', 'user_type': user_type}

    # 测试用户
    if user_type == 'test':
        first_login = user_info.get('first_login_date')
        if not first_login:
            return {
                'valid': True,
                'message': '测试用户未开始计时',
                'user_type': user_type,
            }

        try:
            first_login_date = datetime.fromisoformat(first_login)
            days_elapsed = (datetime.now() - first_login_date).days
            remaining_days = 7 - days_elapsed

            if remaining_days <= 0:
                return {
                    'valid': False,
                    'message': '测试期已过期',
                    'user_type': user_type,
                }
            else:
                return {
                    'valid': True,
                    'message': (
                        f'测试用户，剩余{remaining_days}天'
                    ),
                    'remaining_days': remaining_days,
                    'user_type': user_type
                }
        except (ValueError, TypeError):
            return {
                'valid': True,
                'message': '测试用户',
                'user_type': user_type,
            }

    # 按月付费用户
    if user_type == 'monthly':
        expiry_date = user_info.get('expiry_date')
        remaining_calculations = user_info.get('remaining_calculations', 0)

        if not expiry_date:
            return {'valid': False, 'message': '订阅信息不完整'}

        try:
            expiry = datetime.fromisoformat(expiry_date)
            today = date.today()
            days_remaining = (expiry.date() - today).days
            # 剩余天数为0视为已到期（按日期差）
            if days_remaining <= 0:
                return {
                    'valid': False,
                    'message': '订阅已过期',
                    'remaining_days': 0,
                    'remaining_calculations': remaining_calculations,
                    'user_type': user_type
                }

            # 格式化计算次数显示
            if remaining_calculations == -1:
                calculations_display = "无限次"
            else:
                calculations_display = f"{remaining_calculations}次"

            return {
                'valid': True,
                'message': (
                    f'按月付费用户，剩余{days_remaining}天，'
                    f'剩余{calculations_display}计算'
                ),
                'remaining_days': days_remaining,
                'remaining_calculations': remaining_calculations,
                'user_type': user_type,
            }
        except (ValueError, TypeError):
            return {
                'valid': False,
                'message': '订阅信息错误',
                'user_type': user_type,
            }

    # 企业用户
    if user_type == 'enterprise':
        expiry_date = user_info.get('expiry_date')

        if not expiry_date:
            return {
                'valid': False,
                'message': '订阅信息不完整',
                'user_type': user_type,
            }

        try:
            expiry = datetime.fromisoformat(expiry_date)
            today = date.today()
            days_remaining = (expiry.date() - today).days
            if days_remaining <= 0:
                return {
                    'valid': False,
                    'message': '订阅已过期',
                    'remaining_days': 0,
                    'user_type': user_type
                }
            return {
                'valid': True,
                'message': f'企业版用户，剩余{days_remaining}天',
                'remaining_days': days_remaining,
                'user_type': user_type
            }
        except (ValueError, TypeError):
            return {
                'valid': False,
                'message': '订阅信息错误',
                'user_type': user_type,
            }

    # 处理新的用户类型系统
    if user_type in [
        'free', 'efficiency', 'professional', 'enterprise', 'gratitude',
    ]:
        remaining_calculations = user_info.get('remaining_calculations', 0)

        # 免费版用户：不检查到期时间，仅依据每日计算次数
        if user_type == 'free':
            # 兼容历史数据：免费版不应为-1，若为-1则按10次处理并尝试纠正
            if remaining_calculations == -1:
                try:
                    with get_db_connection() as (fix_conn, fix_cur):
                        fix_cur.execute(
                            "UPDATE users SET remaining_calculations = 10 "
                            "WHERE id = ?",
                            (user_id,)
                        )
                        fix_conn.commit()
                except (sqlite3.Error, OSError, ValueError, TypeError):
                    pass
                remaining_calculations = 10

            calculations_display = f"{remaining_calculations}次"
            return {
                'valid': True,
                'message': (
                    f'免费版用户，剩余{calculations_display}计算'
                ),
                'remaining_calculations': remaining_calculations,
                'user_type': user_type,
            }

        # 非免费版用户：检查订阅过期时间
        # 优先使用subscription_expires字段，如果没有则使用expiry_date
        subscription_expires = user_info.get('subscription_expires')
        expiry_date = user_info.get('expiry_date')

        if subscription_expires:
            # 使用subscription_expires（Unix时间戳）
            import time
            current_time = int(time.time())
            # 确保subscription_expires是整数类型
            subscription_expires = int(subscription_expires)
            # 使用向上取整，确保用户看到完整的剩余天数
            import math
            days_remaining = math.ceil(
                (subscription_expires - current_time) / (24 * 3600)
            )
        elif expiry_date:
            # 使用expiry_date（ISO格式）
            try:
                expiry = datetime.fromisoformat(expiry_date)
                today = date.today()
                days_remaining = (expiry.date() - today).days
            except (ValueError, TypeError):
                return {
                    'valid': False,
                    'message': '订阅信息错误',
                    'user_type': user_type,
                }
        else:
            return {
                'valid': False,
                'message': '订阅信息不完整',
                'user_type': user_type,
            }

        try:
            if days_remaining <= 0:
                return {
                    'valid': False,
                    'message': '订阅到期，请续订',
                    'remaining_days': 0,
                    'remaining_calculations': remaining_calculations,
                    'user_type': user_type
                }
            # 使用友好的用户类型名称
            user_type_display_names = {
                'free': '免费版用户',
                'efficiency': '效率版用户',
                'professional': '专业版用户',
                'enterprise': '企业版用户',
                'gratitude': '感谢版用户',
            }
            display_name = user_type_display_names.get(
                user_type,
                f'{user_type}用户',
            )
            # 格式化计算次数显示
            if remaining_calculations == -1:
                calculations_display = "无限次"
            else:
                calculations_display = f"{remaining_calculations}次"
            return {
                'valid': True,
                'message': (
                    f'{display_name}，剩余{days_remaining}天，'
                    f'剩余{calculations_display}计算'
                ),
                'remaining_days': days_remaining,
                'remaining_calculations': remaining_calculations,
                'user_type': user_type,
            }
        except (ValueError, TypeError):
            return {
                'valid': False,
                'message': '订阅信息错误',
                'user_type': user_type,
            }
    return {'valid': False, 'message': '未知用户类型', 'user_type': user_type}


def decrement_user_calculations(user_id):
    """减少用户计算次数（以 subscription_type 优先判定用户类型）。"""
    with get_db_connection() as (conn, c):
        # 获取当前用户信息（包含 subscription_type 用于优先判断）
        user = c.execute(
            (
                "SELECT user_type, subscription_type, "
                "remaining_calculations FROM users WHERE id = ?"
            ),
            (user_id, ),
        ).fetchone()

        if not user:
            return False

        db_user_type = user[0]
        db_subscription_type = user[1] if len(user) > 1 else None
        remaining = user[2] if len(user) > 2 else -1

        # 以 subscription_type 优先，其次回退到 user_type
        user_type = (db_subscription_type or db_user_type or '').strip()

        # admin用户、永久用户、企业用户、感谢版用户、效率版用户、专业版用户不限制次数
        if user_type in [
                'admin', 'permanent', 'enterprise', 'gratitude',
                'efficiency', 'professional']:
            return True

        # 测试用户不限制次数
        if user_type == 'test':
            return True

        # 免费版用户：按每日次数扣减
        if user_type == 'free':
            if remaining <= 0:
                return False
            c.execute(
                (
                    "UPDATE users SET remaining_calculations = "
                    "remaining_calculations - 1 WHERE id = ? "
                    "AND remaining_calculations > 0"
                ),
                (user_id, )
            )
            conn.commit()
            return c.rowcount > 0

        # 按月付费用户需要检查次数
        if user_type == 'monthly':
            if remaining <= 0:
                return False

            c.execute(
                (
                    "UPDATE users SET remaining_calculations = "
                    "remaining_calculations - 1 WHERE id = ? "
                    "AND remaining_calculations > 0"
                ),
                (user_id, )
            )
            conn.commit()
            return c.rowcount > 0

        return False


def reset_free_users_daily_calculations():
    """每日重置免费用户的计算次数为10次"""
    with get_db_connection() as (conn, c):
        try:
            # 重置所有免费用户的计算次数为10
            c.execute(
                """
                UPDATE users
                SET remaining_calculations = 10
                WHERE user_type = 'free'
                """
            )
            affected_rows = c.rowcount
            conn.commit()

            # 记录日志
            from logger_config import logger
            logger.info(f"每日计算次数重置完成：重置了 {affected_rows} 个免费用户的计算次数")

            return affected_rows
        except Exception as e:
            from logger_config import logger
            logger.error(f"重置免费用户计算次数失败: {e}")
            return 0


def update_user_password(user_id, current_password, new_password):
    """更新用户密码"""
    import bcrypt

    with get_db_connection() as (conn, c):
        # 获取当前用户信息
        user = c.execute(
            "SELECT password FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            return False

        # 验证当前密码
        current_password_bytes = current_password.encode('utf-8')
        stored_password = user['password']

        # 支持旧的SHA256和新的bcrypt密码
        if stored_password.startswith('$2b$'):
            # bcrypt密码
            if not bcrypt.checkpw(current_password_bytes,
                                  stored_password.encode('utf-8')):
                return False
        else:
            # 旧的SHA256密码
            import hashlib
            if (hashlib.sha256(current_password_bytes).hexdigest() !=
                    stored_password):
                return False

        # 使用bcrypt加密新密码
        new_password_bytes = new_password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(new_password_bytes,
                                        salt).decode('utf-8')
        # 更新密码
        c.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_password, user_id)
        )
        conn.commit()
        return True


def delete_user(user_id):
    """删除用户及其相关数据"""

    with get_db_connection() as (conn, c):
        try:
            # 检查用户是否存在
            user = c.execute(
                "SELECT id, username, role FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()

            if not user:
                print(f"删除失败: 用户 ID={user_id} 不存在")
                return False  # 用户不存在

            print(f"准备删除用户: ID={user[0]}, "
                  f"用户名={user[1]}, 角色={user[2]}")

            # 不允许删除admin用户
            if user[2] == 'admin':
                print(f"删除失败: 用户 {user[1]} 是管理员，不允许删除")
                return False

            # 删除用户相关的数据（按外键依赖顺序）
            # 1. 删除用户的产品
            result = c.execute(
                "DELETE FROM products WHERE user_id = ?", (user_id,)
            )
            print(f"删除产品: {result.rowcount} 条")

            # 2. 删除用户的会话记录
            result = c.execute(
                "DELETE FROM active_sessions WHERE user_id = ?", (user_id,)
            )
            print(f"删除会话记录: {result.rowcount} 条")

            # 3. 删除用户的登录尝试记录
            result = c.execute(
                "DELETE FROM login_attempts WHERE identifier = ?", (user[1],)
            )
            print(f"删除登录尝试记录: {result.rowcount} 条")

            # 4. 删除用户的锁定记录
            result = c.execute(
                "DELETE FROM user_lockouts WHERE identifier = ?", (user[1],)
            )
            print(f"删除锁定记录: {result.rowcount} 条")

            # 5. 删除用户的登录/行为日志（统计表中的外键）
            try:
                result = c.execute(
                    "DELETE FROM user_login_log WHERE user_id = ?",
                    (user_id,)
                )
                print(f"删除登录日志: {result.rowcount} 条")
            except sqlite3.OperationalError:
                print("登录日志表不存在，跳过")

            try:
                result = c.execute(
                    "DELETE FROM user_behavior_log WHERE user_id = ?",
                    (user_id,)
                )
                print(f"删除行为日志: {result.rowcount} 条")
            except sqlite3.OperationalError:
                print("行为日志表不存在，跳过")

            # 6. 删除用户的物流规则
            result = c.execute(
                "DELETE FROM logistics WHERE user_id = ?", (user_id,)
            )
            print(f"删除物流规则: {result.rowcount} 条")

            # 7. 删除用户的升级历史（如果表存在）
            try:
                result = c.execute(
                    "DELETE FROM subscription_upgrade_history "
                    "WHERE user_id = ?", (user_id,)
                )
                print(f"删除升级历史: {result.rowcount} 条")
            except sqlite3.OperationalError:
                print("升级历史表不存在，跳过")

            # 8. 删除用户的支付订单
            result = c.execute(
                "DELETE FROM payment_orders WHERE user_id = ?", (user_id,)
            )
            print(f"删除支付订单: {result.rowcount} 条")

            # 9. 清理与用户相关的管理员操作日志/告警记录
            try:
                result = c.execute(
                    "DELETE FROM admin_action_log WHERE admin_id = ? "
                    "OR target_user_id = ?",
                    (user_id, user_id)
                )
                print(f"删除管理员操作日志: {result.rowcount} 条")
            except sqlite3.OperationalError:
                print("管理员操作日志表不存在，跳过")

            try:
                result = c.execute(
                    "UPDATE alert_records SET handled_by = NULL "
                    "WHERE handled_by = ?",
                    (user_id,)
                )
                print(f"置空告警处理人: {result.rowcount} 条")
            except sqlite3.OperationalError:
                print("告警记录表不存在，跳过")

            # 10. 删除用户本身
            result = c.execute("DELETE FROM users WHERE id = ?", (user_id,))
            print(f"删除用户: {result.rowcount} 条")

            conn.commit()
            print(f"✅ 成功删除用户 {user[1]} (ID={user_id})")
            return True

        except sqlite3.Error as e:
            print(f"❌ 数据库错误: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False
        except (Exception,) as e:
            print(f"❌ 删除用户失败: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False


def get_user_preferred_mode(user_id):
    """获取用户的模式偏好"""
    with get_db_connection() as (conn, c):
        result = c.execute(
            "SELECT preferred_mode FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if result:
            return result[0]  # 返回实际值，可能是None（首次登录）、'fast'或'precise'
        return None  # 用户不存在时返回None


def update_user_preferred_mode(user_id, mode):
    """更新用户的模式偏好"""
    with get_db_connection() as (conn, c):
        c.execute(
            "UPDATE users SET preferred_mode = ? WHERE id = ?",
            (mode, user_id)
        )
        conn.commit()


def migrate_user_preferences():
    """迁移现有用户的模式偏好"""
    with get_db_connection() as (conn, c):
        try:
            # 检查preferred_mode列是否存在
            c.execute("PRAGMA table_info(users)")
            columns = [column[1] for column in c.fetchall()]

            if 'preferred_mode' not in columns:
                # 添加preferred_mode列
                c.execute(
                    (
                        "ALTER TABLE users ADD COLUMN preferred_mode TEXT "
                        "DEFAULT 'fast'"
                    )
                )
                conn.commit()
                print("已为users表添加preferred_mode列")

            # 检查是否还有用户没有设置偏好模式
            c.execute(
                "SELECT COUNT(*) FROM users WHERE preferred_mode IS NULL"
            )
            null_count = c.fetchone()[0]

            if null_count > 0:
                # 为所有现有用户设置默认偏好为极速模式
                c.execute(
                    "UPDATE users SET preferred_mode = 'fast' "
                    "WHERE preferred_mode IS NULL"
                )
                conn.commit()
                print(f"已为 {null_count} 个用户设置默认模式偏好")
            # 如果没有需要设置的用户，则不显示任何信息

        except (Exception,) as e:
            print(f"迁移用户偏好失败: {e}")
            conn.rollback()

# 管理员后台相关函数


def authenticate_admin(username, password):
    """验证管理员登录"""
    with get_db_connection() as (conn, c):
        c.execute(
            (
                "SELECT id, username, password, role, email "
                "FROM users "
                "WHERE username = ? AND role = 'admin'"
            ),
            (username,),
        )
        result = c.fetchone()

        if result:
            admin_id, username, password_hash, role, email = result
            import bcrypt
            if bcrypt.checkpw(
                password.encode('utf-8'), password_hash.encode('utf-8')
            ):
                # 更新最后登录时间
                c.execute(
                    (
                        "UPDATE users SET last_login = datetime('now') "
                        "WHERE id = ?"
                    ),
                    (admin_id,),
                )
                conn.commit()
                return {
                    'id': admin_id,
                    'username': username,
                    'role': role,
                    'email': email,
                }
        return None


@st.cache_data(ttl=60)  # 缓存1分钟，用户列表变化不频繁
def get_all_users(
        page=1,
        per_page=20,
        search=None,
        user_type_filter=None,
        status_filter=None,
):
    """获取所有用户列表（分页）"""
    with get_db_connection() as (conn, c):
        # 构建查询条件
        where_conditions = []
        params = []

        if search:
            where_conditions.append("(username LIKE ? OR email LIKE ?)")
            params.extend([f'%{search}%', f'%{search}%'])

        if user_type_filter and user_type_filter != 'all':
            where_conditions.append("user_type = ?")
            params.append(user_type_filter)

        if status_filter:
            if status_filter == 'expired':
                where_conditions.append(
                    "(subscription_end IS NOT NULL AND "
                    "subscription_end < datetime('now'))"
                )
            elif status_filter == 'expiring_soon':
                where_conditions.append(
                    "(subscription_end IS NOT NULL AND subscription_end "
                    "BETWEEN datetime('now') AND datetime('now', '+7 days'))"
                )
            elif status_filter == 'active':
                where_conditions.append(
                    "(subscription_end IS NULL OR "
                    "subscription_end >= datetime('now'))"
                )

        where_clause = (
            " AND ".join(where_conditions) if where_conditions else "1=1"
        )

        # 获取总数
        count_query = f"SELECT COUNT(*) FROM users WHERE {where_clause}"
        c.execute(count_query, params)
        total_count = c.fetchone()[0]

        # 获取分页数据
        offset = (page - 1) * per_page
        query = f"""
        SELECT id, username, email, role, user_type,
               subscription_start, subscription_end,
               remaining_calculations, logistics_templates_limit,
               is_auto_renew, created_at, last_login, is_frozen
        FROM users
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """
        c.execute(query, params + [per_page, offset])
        users = c.fetchall()

        # 获取每个用户的物流模板数量
        user_logistics_counts = {}
        for user in users:
            user_id = user[0]
            c.execute(
                "SELECT COUNT(*) FROM logistics WHERE user_id = ?",
                (user_id,),
            )
            logistics_count = c.fetchone()[0]
            user_logistics_counts[user_id] = logistics_count

        # 格式化用户数据
        formatted_users = []
        for user in users:
            (user_id, username, email, role, user_type, subscription_start,
             subscription_end, remaining_calculations,
             logistics_templates_limit, is_auto_renew, created_at,
             last_login, is_frozen) = user

            # 计算剩余天数
            remaining_days = None
            if subscription_end:
                from datetime import datetime, date
                try:
                    expiry = datetime.fromisoformat(subscription_end)
                    today = date.today()
                    remaining_days = (expiry.date() - today).days
                except (ValueError, TypeError):
                    pass

            formatted_users.append({
                'id': user_id,
                'username': username,
                'email': email,
                'role': role,
                'user_type': user_type,
                'subscription_start': subscription_start,
                'subscription_end': subscription_end,
                'remaining_days': remaining_days,
                'remaining_calculations': remaining_calculations,
                'logistics_templates_limit': logistics_templates_limit,
                'current_logistics_count': user_logistics_counts.get(
                    user_id, 0
                ),
                'is_auto_renew': is_auto_renew,
                'created_at': created_at,
                'last_login': last_login,
                'is_frozen': is_frozen
            })

        return {
            'users': formatted_users,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page,
            'current_page': page
        }


def get_user_detail(user_id):
    """获取用户详细信息"""
    with get_db_connection() as (conn, c):
        c.execute(
            (
                "SELECT id, username, email, role, user_type, "
                "subscription_start, subscription_end, "
                "remaining_calculations, logistics_templates_limit, "
                "is_auto_renew, created_at, last_login, "
                "is_frozen FROM users WHERE id = ?"
            ),
            (user_id,),
        )
        user = c.fetchone()

        if not user:
            return None

        (
            user_id, username, email, role, user_type, subscription_start,
            subscription_end, remaining_calculations,
            logistics_templates_limit, is_auto_renew, created_at,
            last_login, is_frozen,
        ) = user

        # 获取物流模板数量
        c.execute(
            "SELECT COUNT(*) FROM logistics WHERE user_id = ?",
            (user_id,),
        )
        logistics_count = c.fetchone()[0]

        # 获取产品数量
        c.execute(
            "SELECT COUNT(*) FROM products WHERE user_id = ?",
            (user_id,),
        )
        products_count = c.fetchone()[0]

        # 计算剩余天数
        remaining_days = None
        if subscription_end:
            from datetime import datetime, date
            try:
                expiry = datetime.fromisoformat(subscription_end)
                today = date.today()
                remaining_days = (expiry.date() - today).days
            except (ValueError, TypeError):
                pass

        return {
            'id': user_id,
            'username': username,
            'email': email,
            'role': role,
            'user_type': user_type,
            'subscription_start': subscription_start,
            'subscription_end': subscription_end,
            'remaining_days': remaining_days,
            'remaining_calculations': remaining_calculations,
            'logistics_templates_limit': logistics_templates_limit,
            'current_logistics_count': logistics_count,
            'products_count': products_count,
            'is_auto_renew': is_auto_renew,
            'created_at': created_at,
            'last_login': last_login,
            'is_frozen': is_frozen
        }


def update_user_subscription_admin(user_id, updates, admin_id):
    """管理员更新用户订阅信息"""
    with get_db_connection() as (conn, c):
        # 构建更新字段
        set_clauses = []
        values = []

        for field, value in updates.items():
            if field in [
                'user_type', 'subscription_start', 'subscription_end',
                'remaining_calculations', 'logistics_templates_limit',
                'is_auto_renew', 'is_frozen',
            ]:
                set_clauses.append(f"{field} = ?")
                values.append(value)

        if not set_clauses:
            return False

        values.append(user_id)

        # 执行更新
        query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
        c.execute(query, values)

        if c.rowcount > 0:
            # 记录审计日志（保留兼容性）
            details_pairs = [f"{k}={v}" for k, v in updates.items()]
            action_details = (
                "管理员更新用户订阅: " + ", ".join(details_pairs)
            )
            c.execute(
                """
                INSERT INTO audit_logs (admin_id, user_id, action, details)
                VALUES (?, ?, ?, ?)
                """,
                (admin_id, user_id, 'update_subscription', action_details),
            )

            conn.commit()

            # 记录新的操作日志
            try:
                log_admin_action(
                    admin_id=admin_id,
                    action_type='更新订阅',
                    action_detail=action_details,
                    target_user_id=user_id,
                    target_type='subscription'
                )
            except Exception as e:
                print(f"记录管理员操作日志失败: {e}")

            return True

        return False


def freeze_user(user_id, admin_id):
    """冻结用户"""
    with get_db_connection() as (conn, c):
        c.execute("UPDATE users SET is_frozen = 1 WHERE id = ?", (user_id,))

        if c.rowcount > 0:
            # 记录审计日志（保留兼容性）
            c.execute("""
            INSERT INTO audit_logs (admin_id, user_id, action, details)
            VALUES (?, ?, ?, ?)
            """, (admin_id, user_id, 'freeze_user', '管理员冻结用户'))

            conn.commit()

            # 记录新的操作日志
            try:
                log_admin_action(
                    admin_id=admin_id,
                    action_type='冻结用户',
                    action_detail=f'管理员冻结了用户ID: {user_id}',
                    target_user_id=user_id,
                    target_type='user'
                )
            except Exception as e:
                print(f"记录管理员操作日志失败: {e}")

            return True

        return False


def unfreeze_user(user_id, admin_id):
    """解冻用户"""
    with get_db_connection() as (conn, c):
        c.execute("UPDATE users SET is_frozen = 0 WHERE id = ?", (user_id,))

        if c.rowcount > 0:
            # 记录审计日志（注意：原代码有bug，参数数量不对）
            c.execute("""
            INSERT INTO audit_logs (admin_id, user_id, action, details)
            VALUES (?, ?, ?, ?)
            """, (admin_id, user_id, 'unfreeze_user', '管理员解冻用户'))

            conn.commit()

            # 记录新的操作日志
            try:
                log_admin_action(
                    admin_id=admin_id,
                    action_type='解冻用户',
                    action_detail=f'管理员解冻了用户ID: {user_id}',
                    target_user_id=user_id,
                    target_type='user'
                )
            except Exception as e:
                print(f"记录管理员操作日志失败: {e}")

            return True

        return False


def delete_user_admin(user_id, admin_id):
    """管理员删除用户"""
    with get_db_connection() as (conn, c):
        # 保护管理员账号：禁止删除 admin 及其数据
        user_role_row = c.execute(
            "SELECT role, username FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if user_role_row and user_role_row[0] == 'admin':
            print("删除失败: 不允许删除管理员账号及其数据")
            return False

        # 获取用户信息用于日志
        user = c.execute(
            "SELECT username FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        username = user[0] if user else f"ID:{user_id}"

        # 先删除用户相关的数据
        c.execute("DELETE FROM logistics WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM products WHERE user_id = ?", (user_id,))

        # 删除用户
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))

        if c.rowcount > 0:
            # 记录审计日志（保留兼容性）
            c.execute("""
            INSERT INTO audit_logs (admin_id, user_id, action, details)
            VALUES (?, ?, ?, ?)
            """, (admin_id, user_id, 'delete_user', '管理员删除用户'))

            conn.commit()

            # 记录新的操作日志
            try:
                log_admin_action(
                    admin_id=admin_id,
                    action_type='删除用户',
                    action_detail=f'管理员删除了用户: {username} (ID: {user_id})',
                    target_user_id=user_id,
                    target_type='user'
                )
            except Exception as e:
                print(f"记录管理员操作日志失败: {e}")

            return True

        return False


def batch_update_users(user_ids, updates, admin_id):
    """批量更新用户"""
    with get_db_connection() as (conn, c):
        success_count = 0

        for user_id in user_ids:
            # 构建更新字段
            set_clauses = []
            values = []

            for field, value in updates.items():
                if field in [
                    'user_type', 'subscription_start', 'subscription_end',
                    'remaining_calculations', 'logistics_templates_limit',
                    'is_auto_renew', 'is_frozen',
                ]:
                    set_clauses.append(f"{field} = ?")
                    values.append(value)

            if set_clauses:
                values.append(user_id)
                query = (
                    f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
                )
                c.execute(query, values)

                if c.rowcount > 0:
                    success_count += 1
                    # 记录审计日志
                    details_pairs = [f"{k}={v}" for k, v in updates.items()]
                    action_details = "批量更新: " + ", ".join(details_pairs)
                    c.execute("""
                    INSERT INTO audit_logs (admin_id, user_id, action, details)
                    VALUES (?, ?, ?, ?)
                    """, (admin_id, user_id, 'batch_update', action_details))

        conn.commit()
        return success_count


def get_audit_logs(
        page=1,
        per_page=50,
        admin_id=None,
        user_id=None,
        action=None,
):
    """获取审计日志"""
    with get_db_connection() as (conn, c):
        # 构建查询条件
        where_conditions = []
        params = []

        if admin_id:
            where_conditions.append("audit_logs.admin_id = ?")
            params.append(admin_id)

        if user_id:
            where_conditions.append("audit_logs.user_id = ?")
            params.append(user_id)

        if action:
            where_conditions.append("audit_logs.action = ?")
            params.append(action)

        where_clause = (
            " AND ".join(where_conditions) if where_conditions else "1=1"
        )

        # 获取总数
        count_query = f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}"
        c.execute(count_query, params)
        total_count = c.fetchone()[0]

        # 获取分页数据
        offset = (page - 1) * per_page
        query = (
            "SELECT audit_logs.id, audit_logs.admin_id, audit_logs.user_id, "
            "audit_logs.action, audit_logs.details, audit_logs.timestamp, "
            "a.username as admin_username, "
            "u.username as user_username "
            "FROM audit_logs "
            "LEFT JOIN users a ON audit_logs.admin_id = a.id "
            "AND a.role = 'admin' "
            "LEFT JOIN users u ON audit_logs.user_id = u.id "
            f"WHERE {where_clause} "
            "ORDER BY audit_logs.timestamp DESC "
            "LIMIT ? OFFSET ?"
        )
        c.execute(query, params + [per_page, offset])
        logs = c.fetchall()

        formatted_logs = []
        for log in logs:
            (log_id, admin_id, user_id, action, details, timestamp,
             admin_username, user_username) = log
            formatted_logs.append({
                'id': log_id,
                'admin_id': admin_id,
                'user_id': user_id,
                'action': action,
                'details': details,
                'timestamp': timestamp,
                'admin_username': admin_username,
                'user_username': user_username
            })

        return {
            'logs': formatted_logs,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page,
            'current_page': page
        }


def reset_user_password(user_id, admin_id):
    """重置用户密码"""
    import secrets
    import string

    # 生成随机密码
    alphabet = string.ascii_letters + string.digits
    new_password = ''.join(secrets.choice(alphabet) for _ in range(12))

    # 加密密码
    import bcrypt
    password_hash = bcrypt.hashpw(
        new_password.encode('utf-8'), bcrypt.gensalt()
    )

    with get_db_connection() as (conn, c):
        c.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (password_hash.decode('utf-8'), user_id),
        )

        if c.rowcount > 0:
            # 记录审计日志（保留兼容性）
            details_text = f'管理员重置密码: {new_password}'
            c.execute(
                """
                INSERT INTO audit_logs (admin_id, user_id, action, details)
                VALUES (?, ?, ?, ?)
                """,
                (
                    admin_id,
                    user_id,
                    'reset_password',
                    details_text,
                ),
            )

            conn.commit()

            # 记录新的操作日志（不记录密码）
            try:
                log_admin_action(
                    admin_id=admin_id,
                    action_type='重置密码',
                    action_detail=f'管理员重置了用户ID: {user_id} 的密码',
                    target_user_id=user_id,
                    target_type='user'
                )
            except Exception as e:
                print(f"记录管理员操作日志失败: {e}")

            return new_password

        return None


# ============= 统计与运营看板相关函数 =============


def log_user_login(user_id: int, ip_address: Optional[str] = None,
                   user_agent: Optional[str] = None) -> bool:
    """记录用户登录日志"""
    with get_db_connection() as (conn, c):
        try:
            # 简单的设备类型判断
            device_type = 'unknown'
            if user_agent:
                user_agent_lower = user_agent.lower()
                if ('mobile' in user_agent_lower or
                        'android' in user_agent_lower):
                    device_type = 'mobile'
                elif ('tablet' in user_agent_lower or
                        'ipad' in user_agent_lower):
                    device_type = 'tablet'
                else:
                    device_type = 'desktop'

            login_time = int(time.time())
            c.execute("""
                INSERT INTO user_login_log
                (user_id, login_time, ip_address, user_agent, device_type)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, login_time, ip_address, user_agent, device_type))

            # 更新用户的最后登录时间
            c.execute("""
                UPDATE users
                SET last_login = datetime('now')
                WHERE id = ?
            """, (user_id,))

            conn.commit()
            return True
        except Exception as e:
            print(f"记录用户登录日志失败: {e}")
            return False


def log_user_behavior(user_id: int, behavior_type: str,
                      behavior_detail: Optional[str] = None,
                      calculation_mode: Optional[str] = None) -> bool:
    """
    记录用户行为日志

    Args:
        user_id: 用户ID
        behavior_type: 行为类型 (calculation/mode_switch/export等)
        behavior_detail: 行为详细信息（JSON格式）
        calculation_mode: 计算模式（fast/complete）

    Returns:
        bool: 记录是否成功
    """
    with get_db_connection() as (conn, c):
        try:
            c.execute("""
                INSERT INTO user_behavior_log
                (user_id, behavior_type, behavior_detail, calculation_mode)
                VALUES (?, ?, ?, ?)
            """, (user_id, behavior_type, behavior_detail, calculation_mode))
            conn.commit()
            return True
        except Exception as e:
            print(f"记录用户行为日志失败: {e}")
            return False


def log_admin_action(admin_id: int, action_type: str, action_detail: str,
                     target_user_id: Optional[int] = None,
                     target_type: Optional[str] = None,
                     ip_address: Optional[str] = None) -> bool:
    """记录管理员操作日志"""
    with get_db_connection() as (conn, c):
        try:
            c.execute("""
                INSERT INTO admin_action_log
                (admin_id, action_type, action_detail, target_user_id,
                 target_type, ip_address)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (admin_id, action_type, action_detail, target_user_id,
                  target_type, ip_address))
            conn.commit()
            return True
        except Exception as e:
            print(f"记录管理员操作日志失败: {e}")
            return False


def create_alert(alert_type: str, alert_level: str, description: str,
                 threshold_value: Optional[float] = None,
                 actual_value: Optional[float] = None) -> bool:
    """创建异常告警记录"""
    with get_db_connection() as (conn, c):
        try:
            c.execute("""
                INSERT INTO alert_records
                (alert_type, alert_level, description,
                 threshold_value, actual_value)
                VALUES (?, ?, ?, ?, ?)
            """, (alert_type, alert_level, description,
                  threshold_value, actual_value))
            conn.commit()
            return True
        except Exception as e:
            print(f"创建告警记录失败: {e}")
            return False


def get_statistics_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """获取统计缓存数据"""
    with get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            result = c.execute("""
                SELECT cache_data FROM statistics_cache
                WHERE cache_key = ? AND expires_at > ?
            """, (cache_key, current_time)).fetchone()

            if result:
                return json.loads(result[0])
            return None
        except Exception as e:
            print(f"获取缓存失败: {e}")
            return None


def set_statistics_cache(cache_key: str, cache_data: Dict[str, Any],
                         ttl: int = 300) -> bool:
    """设置统计缓存数据

    Args:
        cache_key: 缓存键
        cache_data: 缓存数据
        ttl: 过期时间（秒），默认5分钟
    """
    with get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            expires_at = current_time + ttl
            cache_json = json.dumps(cache_data, ensure_ascii=False)

            c.execute("""
                INSERT OR REPLACE INTO statistics_cache
                (cache_key, cache_data, expires_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (cache_key, cache_json, expires_at, current_time))
            conn.commit()
            return True
        except Exception as e:
            print(f"设置缓存失败: {e}")
            return False


def clear_expired_cache() -> int:
    """清理过期的缓存数据"""
    with get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            c.execute("""
                DELETE FROM statistics_cache WHERE expires_at < ?
            """, (current_time,))
            conn.commit()
            return c.rowcount
        except Exception as e:
            print(f"清理缓存失败: {e}")
            return 0


def clear_all_statistics_cache() -> int:
    """清除所有统计缓存数据"""
    with get_db_connection() as (conn, c):
        try:
            c.execute("DELETE FROM statistics_cache")
            conn.commit()
            return c.rowcount
        except Exception as e:
            print(f"清除所有缓存失败: {e}")
            return 0


# @st.cache_resource(ttl=300)  # 缓存5分钟 - 临时禁用
def get_dashboard_stats() -> Dict[str, Any]:
    """获取总览看板数据"""
    # 先尝试从缓存获取
    cache_key = "dashboard_stats"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            today_start = current_time - (current_time % 86400)
            yesterday_start = today_start - 86400
            month_start = current_time - (current_time % (30 * 86400))

            # 今日活跃用户数（今日登录的用户）
            active_users_today = c.execute("""
                SELECT COUNT(DISTINCT user_id)
                FROM user_login_log
                WHERE login_time >= ?
            """, (today_start,)).fetchone()[0]

            # 今日新增用户数
            # 将时间戳转换为日期字符串来与created_at比较
            today_start_str = datetime.fromtimestamp(today_start).strftime(
                '%Y-%m-%d 00:00:00'
            )
            new_users_today = c.execute("""
                SELECT COUNT(*) FROM users
                WHERE created_at >= ?
            """, (today_start_str,)).fetchone()[0]

            # 累计注册用户数
            total_users = c.execute("""
                SELECT COUNT(*) FROM users WHERE role != 'admin'
            """).fetchone()[0]

            # 总收入（所有成功支付的订单）
            total_revenue = c.execute("""
                SELECT COALESCE(SUM(amount), 0) / 100.0
                FROM payment_orders
                WHERE status = 'SUCCESS'
            """).fetchone()[0]

            # 今日收入
            revenue_today = c.execute("""
                SELECT COALESCE(SUM(amount), 0) / 100.0
                FROM payment_orders
                WHERE status = 'SUCCESS' AND created_at >= ?
            """, (today_start,)).fetchone()[0]

            # 昨日收入
            revenue_yesterday = c.execute("""
                SELECT COALESCE(SUM(amount), 0) / 100.0
                FROM payment_orders
                WHERE status = 'SUCCESS'
                AND created_at >= ? AND created_at < ?
            """, (yesterday_start, today_start)).fetchone()[0]

            # 本月收入
            revenue_month = c.execute("""
                SELECT COALESCE(SUM(amount), 0) / 100.0
                FROM payment_orders
                WHERE status = 'SUCCESS' AND created_at >= ?
            """, (month_start,)).fetchone()[0]

            # 实时在线用户数（过去5分钟有登录记录的用户）
            online_users = c.execute("""
                SELECT COUNT(DISTINCT user_id)
                FROM user_login_log
                WHERE login_time >= ?
            """, (current_time - 300,)).fetchone()[0]

            result = {
                'active_users_today': active_users_today,
                'new_users_today': new_users_today,
                'total_users': total_users,
                'total_revenue': round(total_revenue, 2),
                'revenue_today': round(revenue_today, 2),
                'revenue_yesterday': round(revenue_yesterday, 2),
                'revenue_month': round(revenue_month, 2),
                'online_users': online_users,
                'timestamp': current_time
            }

            # 缓存5分钟
            set_statistics_cache(cache_key, result, 300)
            return result
        except Exception as e:
            print(f"获取总览数据失败: {e}")
            return {}


# ============================================================================
# 套餐管理CRUD函数
# ============================================================================

@st.cache_data(ttl=300)  # 缓存5分钟，套餐数据变化不频繁
def get_plans(active_only=False, include_free=True):
    """
    获取所有套餐列表

    Args:
        active_only: 是否只获取上架的套餐
        include_free: 是否包含免费版

    Returns:
        list: 套餐列表，每个套餐为dict
    """
    with get_db_connection() as (conn, c):
        try:
            query = "SELECT * FROM plans WHERE 1=1"
            params = []

            if active_only:
                query += " AND is_active = 1"

            if not include_free:
                query += " AND plan_code != 'free'"

            query += " ORDER BY sort_order"

            c.execute(query, params)
            columns = [col[0] for col in c.description]
            rows = c.fetchall()

            plans = []
            for row in rows:
                plan = dict(zip(columns, row))
                plans.append(plan)

            return plans
        except Exception as e:
            print(f"获取套餐列表失败: {e}")
            return []


# @st.cache_data(ttl=300)  # 缓存5分钟 - 暂时禁用以修复测试
def get_plan_by_code(plan_code: str):
    """
    根据套餐代码获取套餐详情

    Args:
        plan_code: 套餐代码

    Returns:
        dict: 套餐详情，不存在返回None
    """
    with get_db_connection() as (conn, c):
        try:
            c.execute("SELECT * FROM plans WHERE plan_code = ?", (plan_code,))
            row = c.fetchone()

            if row:
                columns = [col[0] for col in c.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            print(f"获取套餐详情失败: {e}")
            return None


def get_plan_by_id(plan_id: int):
    """
    根据ID获取套餐详情

    Args:
        plan_id: 套餐ID

    Returns:
        dict: 套餐详情，不存在返回None
    """
    with get_db_connection() as (conn, c):
        try:
            c.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
            row = c.fetchone()

            if row:
                columns = [col[0] for col in c.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            print(f"获取套餐详情失败: {e}")
            return None


def create_plan(
    plan_code: str,
    plan_name: str,
    display_price_month: float,
    display_price_year: float,
    actual_price_month: float,
    actual_price_year: float,
    test_price_month: float = 0.0,
    test_price_year: float = 0.0,
    calc_limit: int = -1,
    logistics_limit: int = 1,
    description: str = "",
    features: str = "",
    is_active: int = 1,
    sort_order: int = 0
):
    """
    创建新套餐

    Returns:
        bool: 成功返回True，失败返回False
    """
    with get_db_connection() as (conn, c):
        try:
            # 检查代码是否已存在
            existing = c.execute(
                "SELECT id FROM plans WHERE plan_code = ?",
                (plan_code,)
            ).fetchone()

            if existing:
                print(f"套餐代码 {plan_code} 已存在")
                return False

            c.execute("""
                INSERT INTO plans (
                    plan_code, plan_name,
                    display_price_month, display_price_year,
                    actual_price_month, actual_price_year,
                    test_price_month, test_price_year,
                    calc_limit, logistics_limit,
                    description, features,
                    is_active, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_code, plan_name,
                display_price_month, display_price_year,
                actual_price_month, actual_price_year,
                test_price_month, test_price_year,
                calc_limit, logistics_limit,
                description, features,
                is_active, sort_order
            ))

            conn.commit()
            return True
        except Exception as e:
            print(f"创建套餐失败: {e}")
            return False


def update_plan(
    plan_id: int,
    **kwargs
):
    """
    更新套餐信息

    Args:
        plan_id: 套餐ID
        **kwargs: 要更新的字段

    Returns:
        bool: 成功返回True，失败返回False
    """
    with get_db_connection() as (conn, c):
        try:
            # 允许更新的字段
            allowed_fields = [
                'plan_name', 'display_price_month', 'display_price_year',
                'actual_price_month', 'actual_price_year',
                'test_price_month', 'test_price_year',
                'calc_limit', 'logistics_limit',
                'description', 'features',
                'is_active', 'sort_order'
            ]

            # 过滤并构建SET子句
            updates = []
            values = []
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = ?")
                    values.append(value)

            if not updates:
                return False

            # 添加updated_at
            updates.append("updated_at = strftime('%s', 'now')")

            query = f"UPDATE plans SET {', '.join(updates)} WHERE id = ?"
            values.append(plan_id)

            c.execute(query, values)
            conn.commit()

            return c.rowcount > 0
        except Exception as e:
            print(f"更新套餐失败: {e}")
            return False


def delete_plan(plan_id: int):
    """
    删除套餐

    Args:
        plan_id: 套餐ID

    Returns:
        bool: 成功返回True，失败返回False
    """
    with get_db_connection() as (conn, c):
        try:
            # 检查是否为免费版（不允许删除）
            plan = c.execute(
                "SELECT plan_code FROM plans WHERE id = ?",
                (plan_id,)
            ).fetchone()

            if plan and plan[0] == 'free':
                print("不允许删除免费版套餐")
                return False

            c.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
            conn.commit()

            return c.rowcount > 0
        except Exception as e:
            print(f"删除套餐失败: {e}")
            return False


def toggle_plan_active(plan_id: int):
    """
    切换套餐上下架状态

    Args:
        plan_id: 套餐ID

    Returns:
        bool: 成功返回True，失败返回False
    """
    with get_db_connection() as (conn, c):
        try:
            c.execute("""
                UPDATE plans
                SET is_active = 1 - is_active,
                    updated_at = strftime('%s', 'now')
                WHERE id = ?
            """, (plan_id,))
            conn.commit()

            return c.rowcount > 0
        except Exception as e:
            print(f"切换套餐状态失败: {e}")
            return False


def get_plan_price(plan_code: str, duration: str,
                   use_test_price: bool = False):
    """
    获取套餐价格（根据用户角色）

    Args:
        plan_code: 套餐代码
        duration: 时长 ('month' 或 'year')
        use_test_price: 是否使用测试价格（管理员使用测试价）

    Returns:
        float: 价格（元），如果套餐不存在返回0
    """
    plan = get_plan_by_code(plan_code)
    if not plan:
        return 0

    if use_test_price:
        # 管理员使用测试价
        if duration == 'year':
            return plan['test_price_year']
        return plan['test_price_month']
    else:
        # 普通用户使用实际价
        if duration == 'year':
            return plan['actual_price_year']
        return plan['actual_price_month']
