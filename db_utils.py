import os
import sqlite3
import streamlit as st
import hashlib
import bcrypt
import threading
import atexit
import queue
from typing import Optional, Tuple
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
    """程序退出时检查连接数"""
    count = get_connection_count()
    if count > 0:
        print(f"⚠️  警告: 程序退出时仍有 {count} 个数据库连接未关闭")

        # 尝试清理连接池
        try:
            while not _CONNECTION_POOL.empty():
                conn = _CONNECTION_POOL.get_nowait()
                conn.close()
        except (Exception,) as e:
            print(f"清理连接池时出错: {e}")


# 注册退出检查
atexit.register(_check_connections_at_exit)


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
    """显式上下文管理器，提供 (conn, cursor) 二元组"""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._cursor: Optional[sqlite3.Cursor] = None

    def __enter__(self) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
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
        cursor = conn.cursor()
        self._conn = conn
        self._cursor = cursor

        # 增加连接计数
        _increment_connection_counter()

        return conn, cursor

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._conn is not None:
            self._conn.close()
            # 减少连接计数
            _decrement_connection_counter()


class PooledDBConnection:
    """连接池上下文管理器"""

    def __init__(self):
        self._conn: Optional[sqlite3.Connection] = None
        self._cursor: Optional[sqlite3.Cursor] = None

    def __enter__(self) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
        # 从池中获取连接
        self._conn = _get_connection_from_pool()
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


def get_db_connection() -> DBConnection:
    """返回一个可用于 with 语句的数据库连接管理器"""
    db_path = os.path.join(os.path.dirname(__file__), "pricing_system.db")
    return DBConnection(db_path)


def get_pooled_db_connection() -> PooledDBConnection:
    """返回一个使用连接池的数据库连接管理器"""
    return PooledDBConnection()


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
            "subscription_expires": "INTEGER"
        }
        for col, def_sql in new_cols.items():
            if col not in cols:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {def_sql}")
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


def create_user(username, password, role="user", email=None, user_type="free"):
    """创建用户"""
    # 确保数据库已初始化
    init_db()

    # 验证用户名
    if not username or len(username.strip()) == 0:
        return False

    # 验证密码强度
    password_validation = validate_password_strength(password)
    if not password_validation['is_valid']:
        return False

    with get_db_connection() as (conn, c):

        # 检查用户名是否已存在（不区分大小写）
        existing_user = c.execute(
            "SELECT username FROM users WHERE LOWER(username) = LOWER(?)",
            (username,)
        ).fetchone()

        if existing_user:
            return False  # 用户名已存在

        # 检查邮箱是否已存在（如果提供了邮箱）
        if email:
            existing_email = c.execute(
                "SELECT email FROM users WHERE LOWER(email) = LOWER(?)",
                (email,)
            ).fetchone()

            if existing_email:
                return False  # 邮箱已存在

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
            if email:
                c.execute(
                    "INSERT INTO users (username, password, role, email, "
                    "user_type, remaining_calculations) VALUES "
                    "(?, ?, ?, ?, ?, ?)",
                    (username, hashed_password, role, email, user_type,
                     remaining_calculations),
                )
            else:
                c.execute(
                    "INSERT INTO users (username, password, role, "
                    "user_type, remaining_calculations) VALUES "
                    "(?, ?, ?, ?, ?)",
                    (username, hashed_password, role, user_type,
                     remaining_calculations),
                )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


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
                return_rate            REAL DEFAULT 0
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
        _upgrade_users_subscription_fields()
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
            'promotion_discount', 'promotion_cost_rate',
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


def get_all_products_for_user(user_id):
    """获取用户的所有产品"""
    with get_db_connection() as (conn, c):
        products = c.execute(
            "SELECT * FROM products WHERE user_id = ?",
            (user_id,)
        ).fetchall()
        return [dict(product) for product in products]


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
            # 计算次数显示
            if remaining_calculations == -1:
                calculations_display = "无限次"
            else:
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
            days_remaining = ((subscription_expires - current_time) //
                              (24 * 3600))
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
    """减少用户计算次数"""
    with get_db_connection() as (conn, c):
        # 获取当前用户信息
        user = c.execute(
            (
                "SELECT user_type, remaining_calculations FROM users"
                " WHERE id = ?"
            ),
            (user_id, ),
        ).fetchone()

        if not user:
            return False

        user_type = user[0]  # user_type在第一列
        remaining = user[1] if len(user) > 1 else -1

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
                return False  # 用户不存在

            # 不允许删除admin用户
            if user[2] == 'admin':
                return False

            # 删除用户相关的数据（按外键依赖顺序）
            # 1. 删除用户的产品
            c.execute("DELETE FROM products WHERE user_id = ?", (user_id,))

            # 2. 删除用户的会话记录
            c.execute(
                "DELETE FROM active_sessions WHERE user_id = ?", (user_id,)
            )

            # 3. 删除用户的登录尝试记录
            c.execute(
                "DELETE FROM login_attempts WHERE identifier = ?", (user[1],)
            )

            # 4. 删除用户的锁定记录
            c.execute(
                "DELETE FROM user_lockouts WHERE identifier = ?", (user[1],)
            )

            # 5. 删除用户的物流规则
            c.execute(
                "DELETE FROM logistics WHERE user_id = ?", (user_id,)
            )

            # 6. 删除用户的支付订单
            c.execute(
                "DELETE FROM payment_orders WHERE user_id = ?", (user_id,)
            )

            # 7. 删除用户本身
            c.execute("DELETE FROM users WHERE id = ?", (user_id,))

            conn.commit()
            return True

        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            conn.rollback()
            return False
        except (Exception,) as e:
            print(f"删除用户失败: {e}")
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
                "SELECT id, username, password_hash, role, email "
                "FROM admin_users "
                "WHERE username = ? AND is_active = 1"
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
                        "UPDATE admin_users SET last_login = datetime('now') "
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
            # 记录审计日志
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
            return True

        return False


def freeze_user(user_id, admin_id):
    """冻结用户"""
    with get_db_connection() as (conn, c):
        c.execute("UPDATE users SET is_frozen = 1 WHERE id = ?", (user_id,))

        if c.rowcount > 0:
            # 记录审计日志
            c.execute("""
            INSERT INTO audit_logs (admin_id, user_id, action, details)
            VALUES (?, ?, ?, ?)
            """, (admin_id, user_id, 'freeze_user', '管理员冻结用户'))

            conn.commit()
            return True

        return False


def unfreeze_user(user_id, admin_id):
    """解冻用户"""
    with get_db_connection() as (conn, c):
        c.execute("UPDATE users SET is_frozen = 0 WHERE id = ?", (user_id,))

        if c.rowcount > 0:
            # 记录审计日志
            c.execute("""
            INSERT INTO audit_logs (admin_id, user_id, action, details)
            VALUES (?, ?, ?, ?, ?)
            """, (admin_id, user_id, 'unfreeze_user', '管理员解冻用户'))

            conn.commit()
            return True

        return False


def delete_user_admin(user_id, admin_id):
    """管理员删除用户"""
    with get_db_connection() as (conn, c):
        # 先删除用户相关的数据
        c.execute("DELETE FROM logistics WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM products WHERE user_id = ?", (user_id,))

        # 删除用户
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))

        if c.rowcount > 0:
            # 记录审计日志
            c.execute("""
            INSERT INTO audit_logs (admin_id, user_id, action, details)
            VALUES (?, ?, ?, ?)
            """, (admin_id, user_id, 'delete_user', '管理员删除用户'))

            conn.commit()
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
            "admin_users.username as admin_username, "
            "users.username as user_username "
            "FROM audit_logs "
            "LEFT JOIN admin_users ON audit_logs.admin_id = admin_users.id "
            "LEFT JOIN users ON audit_logs.user_id = users.id "
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
            # 记录审计日志
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
            return new_password

        return None
