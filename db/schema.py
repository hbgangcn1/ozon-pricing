import logging
import re

from db._proxy import _db
from db.helpers import DB_EXCEPTIONS
from db_adapter import adapt_sql

logger = logging.getLogger(__name__)


def _create_users_table(conn, c):
    users_sql = _db._safe_adapt_sql(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            email TEXT UNIQUE,
            preferred_mode TEXT DEFAULT 'fast'
        )
        """,
        conn,
    )
    c.execute(users_sql)


def _create_products_table(conn, c):
    products_sql = _db._safe_adapt_sql(
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
            has_liquid INTEGER,
            shipping_fee REAL,
            labeling_fee REAL,
            promotion_discount     REAL DEFAULT 0.05,
            promotion_cost_rate    REAL DEFAULT 0.115,
            target_profit_margin   REAL DEFAULT 0.5,
            commission_rate        REAL DEFAULT 0.17,
            withdrawal_fee_rate    REAL DEFAULT 0.01,
            payment_processing_fee REAL DEFAULT 0.01,
            return_rate            REAL DEFAULT 0,
            vat_rate               REAL DEFAULT 0,
            is_test_data           INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        conn,
    )
    c.execute(products_sql)


def _create_logistics_table(conn, c):
    logistics_sql = _db._safe_adapt_sql(
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
            allow_liquid INTEGER,
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
            price_min_currency TEXT DEFAULT 'RUB',
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        conn,
    )
    c.execute(logistics_sql)


def _init_base_tables(conn, c):
    """创建三张基础表：users / products / logistics"""
    _create_users_table(conn, c)
    _create_products_table(conn, c)
    _create_logistics_table(conn, c)
    _db._ensure_serial_columns(conn, c, ["users", "products", "logistics"])


def _fix_system_config_serial(conn, c):
    """修复system_config表id列为serial类型（PostgreSQL）"""
    try:
        c.execute(
            "SELECT data_type, column_default"
            " FROM information_schema.columns"
            " WHERE table_name = 'system_config' AND column_name = 'id'"
        )
        id_col_info = c.fetchone()
        if id_col_info and id_col_info[0] == "integer" and not id_col_info[1]:
            try:
                c.execute("CREATE SEQUENCE IF NOT EXISTS system_config_id_seq")
                c.execute(
                    "ALTER TABLE system_config ALTER COLUMN id"
                    " SET DEFAULT nextval('system_config_id_seq')"
                )
                c.execute(
                    "ALTER SEQUENCE system_config_id_seq OWNED BY system_config.id"
                )
                conn.commit()
            except DB_EXCEPTIONS:
                conn.rollback()

        c.execute(
            "SELECT constraint_name"
            " FROM information_schema.table_constraints"
            " WHERE table_name = 'system_config'"
            " AND constraint_type = 'UNIQUE'"
            " AND constraint_name LIKE '%config_key%'"
        )
        if not c.fetchone():
            c.execute(
                "ALTER TABLE system_config"
                " ADD CONSTRAINT system_config_config_key_unique"
                " UNIQUE (config_key)"
            )
            conn.commit()
    except DB_EXCEPTIONS as e:
        conn.rollback()
        try:
            import psycopg2

            if isinstance(
                e,
                (
                    psycopg2.errors.DuplicateObject,
                    psycopg2.errors.ProgrammingError,
                ),
            ):
                pass
        except (ImportError, AttributeError):
            pass
    except (AttributeError, KeyError, TypeError, RuntimeError):
        conn.rollback()


def _init_system_config_table(conn, c):
    """创建system_config表并初始化默认配置"""
    system_config_sql = adapt_sql(
        """
        CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT UNIQUE NOT NULL,
            config_value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    c.execute(system_config_sql)

    if _db._is_postgresql_connection(conn):
        _fix_system_config_serial(conn, c)
        insert_sql = _db._safe_adapt_sql(
            "INSERT INTO system_config"
            " (config_key, config_value, description)"
            " VALUES (%s, %s, %s)"
            " ON CONFLICT DO NOTHING",
            conn,
        )
    else:
        insert_sql = _db._safe_adapt_sql(
            "INSERT OR IGNORE INTO system_config"
            " (config_key, config_value, description)"
            " VALUES (?, ?, ?)",
            conn,
        )
    c.execute(insert_sql, ("open_registration", "false", "是否开放用户注册"))
    conn.commit()


def _init_payment_table(conn, c):
    """创建payment_orders表"""
    payment_orders_sql = """
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
    """
    adapted_sql = adapt_sql(payment_orders_sql)
    if _db._is_postgresql_connection(conn) and "AUTOINCREMENT" in adapted_sql.upper():
        adapted_sql = re.sub(
            r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
            "SERIAL PRIMARY KEY",
            adapted_sql,
            flags=re.IGNORECASE,
        )
        adapted_sql = re.sub(r"\s+AUTOINCREMENT", "", adapted_sql, flags=re.IGNORECASE)
    c.execute(adapted_sql)


def _init_admin_user(conn, c):
    """初始化管理员用户（如不存在）"""
    is_pg = _db._is_postgresql_connection(conn)
    sql_raw = "SELECT * FROM users WHERE username = ?"
    sql = _db._safe_adapt_sql(sql_raw, conn)
    if is_pg and "?" in sql:
        sql = sql.replace("?", "%s")
    c.execute(sql, ("admin",))
    admin_user = c.fetchone()
    if admin_user:
        return

    hashed_password = _db.hash_password("admin123")
    cols = _db._get_table_columns(c, "users")
    has_user_type = "user_type" in cols

    if has_user_type:
        sql_raw = (
            "INSERT INTO users (username, password, role, email, user_type)"
            " VALUES (?, ?, ?, ?, ?)"
        )
        sql = _db._safe_adapt_sql(sql_raw, conn)
        if is_pg and "?" in sql:
            sql = sql.replace("?", "%s")
        c.execute(
            sql,
            ("admin", hashed_password, "admin", "admin@example.com", "permanent"),
        )
    else:
        sql_raw = (
            "INSERT INTO users (username, password, role, email) VALUES (?, ?, ?, ?)"
        )
        sql = _db._safe_adapt_sql(sql_raw, conn)
        if is_pg and "?" in sql:
            sql = sql.replace("?", "%s")
        c.execute(
            sql,
            ("admin", hashed_password, "admin", "admin@example.com"),
        )
    conn.commit()


def _init_trigger_cleanup(conn, c):
    try:
        if _db._is_postgresql_connection(conn):
            c.execute(
                "DROP TRIGGER IF EXISTS trg_prevent_delete_admin_products ON products"
            )
        else:
            c.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_admin_products")
        conn.commit()
    except DB_EXCEPTIONS:
        pass


def init_db():
    """初始化数据库"""
    with _db.get_db_connection() as (conn, c):
        _init_base_tables(conn, c)
        _init_system_config_table(conn, c)
        _init_payment_table(conn, c)
        _init_admin_user(conn, c)
        _init_trigger_cleanup(conn, c)
        _db._ensure_serial_columns(conn, c)


def _ensure_postgresql_schema(conn, cursor):
    """确保PostgreSQL schema存在 - 执行完整的schema自愈流程"""
    if not _db._is_postgresql_connection(conn):
        return

    _db._ensure_serial_primary_key(conn, cursor, "users", "id")
    _db._ensure_serial_primary_key(conn, cursor, "products", "id")
    _db._ensure_serial_primary_key(conn, cursor, "payment_orders", "id")

    _db._ensure_unique_constraint(
        conn, cursor, "users", ("username",), "users_username_key"
    )

    _db._cleanup_duplicate_rows(conn, "users", ("username",))
    _db._cleanup_duplicate_ids(conn, cursor, "users")

    _db._ensure_foreign_key(
        conn, cursor, "products", "fk_products_user_id", "user_id", "users", "id"
    )

    conn.commit()


def _cleanup_duplicate_rows(conn, table_name, unique_columns):
    import re as _re

    if not unique_columns:
        return
    if not _re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
        return
    for col in unique_columns:
        if not _re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col):
            return

    cursor = conn.cursor()
    try:
        cols = ", ".join(unique_columns)
        sql = (
            f"DELETE FROM {table_name} "
            f"WHERE ctid NOT IN ("
            f"SELECT MIN(ctid) FROM {table_name} "
            f"GROUP BY {cols})"
        )
        cursor.execute(sql)
        conn.commit()
    except Exception:
        logger.debug("清理重复行失败，尝试回滚", exc_info=True)
        try:
            conn.rollback()
        except Exception:
            logger.debug("回滚失败", exc_info=True)


def _cleanup_duplicate_ids(conn, table_name_or_cursor, id_column_or_table=None):
    import re as _re

    if id_column_or_table is not None and isinstance(id_column_or_table, str):
        if hasattr(table_name_or_cursor, "execute"):
            cursor = table_name_or_cursor
            table_name = id_column_or_table
        else:
            return 0
    elif hasattr(table_name_or_cursor, "execute"):
        return 0
    else:
        return 0

    if not _re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
        return 0

    try:
        sql = (
            f"DELETE FROM {table_name} "
            f"WHERE ctid NOT IN ("
            f"SELECT MIN(ctid) FROM {table_name} "
            f"GROUP BY id)"
        )
        cursor.execute(sql)
        conn.commit()
    except Exception:
        logger.debug("清理重复ID失败，尝试回滚", exc_info=True)
        try:
            conn.rollback()
        except Exception:
            logger.debug("回滚失败", exc_info=True)
    return 0


def _ensure_serial_primary_key(conn, cursor, table_name, column_name="id"):
    import re as _re

    if not _re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
        return

    seq_name = f"{table_name}_{column_name}_seq"
    try:
        cursor.execute(
            "SELECT column_default FROM information_schema.columns"
            " WHERE table_name = %s AND column_name = %s",
            (table_name, column_name),
        )
        row = cursor.fetchone()
        if row and row[0] and "nextval" in str(row[0]):
            return

        cursor.execute(
            "SELECT 1 FROM pg_sequences WHERE schemaname = 'public'"
            " AND sequencename = %s",
            (seq_name,),
        )
        seq_exists = cursor.fetchone()
        if not seq_exists:
            cursor.execute(f"CREATE SEQUENCE {seq_name}")

        cursor.execute(
            f"ALTER TABLE {table_name} ALTER COLUMN {column_name}"
            f" SET DEFAULT nextval('{seq_name}')"
        )
        cursor.execute(f"ALTER SEQUENCE {seq_name} OWNED BY {table_name}.{column_name}")
        cursor.execute(f"SELECT MAX({column_name}) FROM {table_name}")
        max_row = cursor.fetchone()
        if max_row and max_row[0]:
            cursor.execute(f"SELECT setval('{seq_name}', %s)", (max_row[0],))
    except Exception:
        logger.debug("确保serial主键失败，尝试回滚", exc_info=True)
        try:
            conn.rollback()
        except Exception:
            logger.debug("回滚失败", exc_info=True)


def _ensure_unique_constraint(
    conn, cursor, table_name, columns_or_name, name_or_columns=None
):
    import re as _re

    if isinstance(columns_or_name, (tuple, list)):
        columns = tuple(columns_or_name)
        constraint_name = name_or_columns or f"{table_name}_{'_'.join(columns)}_key"
    elif isinstance(name_or_columns, (tuple, list)):
        columns = tuple(name_or_columns)
        constraint_name = columns_or_name
    else:
        constraint_name = columns_or_name
        columns = (name_or_columns,) if name_or_columns else ()

    if not columns:
        return
    if not _re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
        return

    try:
        cursor.execute(
            "SELECT 1 FROM information_schema.table_constraints"
            " WHERE table_name = %s AND constraint_name = %s"
            " AND constraint_type = 'UNIQUE'",
            (table_name, constraint_name),
        )
        exists = cursor.fetchone()
        cursor.fetchall()
        if exists:
            return

        cols = ", ".join(columns)
        cursor.execute(
            f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} UNIQUE ({cols})"
        )
        conn.commit()
    except Exception:
        logger.debug("确保唯一约束失败，尝试回滚", exc_info=True)
        try:
            conn.rollback()
        except Exception:
            logger.debug("回滚失败", exc_info=True)


def _ensure_foreign_key(
    conn, cursor, table_name, constraint_name, column, ref_table, ref_column
):
    pass
