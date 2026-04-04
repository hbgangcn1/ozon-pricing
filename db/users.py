import logging
import threading
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence, cast

from db._proxy import _db

logger = logging.getLogger(__name__)

_db_initialized_cache = {"initialized": False, "lock": threading.Lock()}


def _create_user_with_email(
    conn,
    c,
    username,
    hashed_password,
    role,
    email,
    user_type,
    remaining_calculations,
    created_at_ts,
    is_test,
):
    sql_raw = (
        "INSERT INTO users (username, password, role, email, "
        "user_type, subscription_type, "
        "remaining_calculations, "
        "created_at, is_test_user) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, to_timestamp(?), ?) "
        "RETURNING id"
    )
    sql = _db._safe_adapt_sql(sql_raw, conn)
    c.execute(
        sql,
        (
            username,
            hashed_password,
            role,
            email,
            user_type,
            user_type,
            remaining_calculations,
            created_at_ts,
            is_test,
        ),
    )
    return c.fetchone()[0]


def _create_user_without_email(
    conn,
    c,
    username,
    hashed_password,
    role,
    user_type,
    remaining_calculations,
    created_at_ts,
    is_test,
):
    sql_raw = (
        "INSERT INTO users (username, password, role, "
        "user_type, subscription_type, "
        "remaining_calculations, "
        "created_at, is_test_user) "
        "VALUES (?, ?, ?, ?, ?, ?, to_timestamp(?), ?) "
        "RETURNING id"
    )
    sql = _db._safe_adapt_sql(sql_raw, conn)
    c.execute(
        sql,
        (
            username,
            hashed_password,
            role,
            user_type,
            user_type,
            remaining_calculations,
            created_at_ts,
            is_test,
        ),
    )
    return c.fetchone()[0]


def _get_remaining_calculations(user_type):
    if user_type == "free":
        return 10
    elif user_type in ["test", "gratitude", "efficiency", "professional", "enterprise"]:
        return -1
    else:
        return 10


def create_user(
    username, password, role="user", email=None, user_type="free", is_test_user=False
):
    _db.init_db()

    if not username or len(username.strip()) == 0:
        return None

    password_validation = _db.validate_password_strength(password)
    if not password_validation["is_valid"]:
        return None

    with _db.get_db_connection() as (conn, c):
        sql_raw = "SELECT username FROM users WHERE LOWER(username) = LOWER(?)"
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (username,))
        existing_user = c.fetchone()

        if existing_user:
            return None

        if email:
            sql_raw = "SELECT email FROM users WHERE LOWER(email) = LOWER(?)"
            sql = _db._safe_adapt_sql(sql_raw, conn)
            existing_email = _db._safe_execute_fetchone(c, sql, (email,), conn)
            if existing_email:
                return None

        hashed_password = _db.hash_password(password)
        remaining_calculations = _get_remaining_calculations(user_type)

        try:
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            is_test = 1 if is_test_user else 0
            created_at_ts = int(
                datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").timestamp()
            )

            if email:
                if _db._is_postgresql_connection(conn):
                    user_id = _create_user_with_email(
                        conn,
                        c,
                        username,
                        hashed_password,
                        role,
                        email,
                        user_type,
                        remaining_calculations,
                        created_at_ts,
                        is_test,
                    )
            else:
                if _db._is_postgresql_connection(conn):
                    user_id = _create_user_without_email(
                        conn,
                        c,
                        username,
                        hashed_password,
                        role,
                        user_type,
                        remaining_calculations,
                        created_at_ts,
                        is_test,
                    )
            conn.commit()
            return user_id
        except Exception as e:
            logger.warning("创建用户失败: %s", e)
            return None


def verify_user(identifier, password):
    with _db_initialized_cache["lock"]:
        if not _db_initialized_cache["initialized"]:
            try:
                with _db.get_db_connection() as (conn, c):
                    check_sql = """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_name = 'users'
                            LIMIT 1
                        )
                    """
                    c.execute(check_sql)
                    table_exists = c.fetchone()
                    if table_exists and (
                        (isinstance(table_exists, bool) and table_exists)
                        or (isinstance(table_exists, tuple) and table_exists[0])
                    ):
                        _db_initialized_cache["initialized"] = True
                    else:
                        _db.init_db()
                        _db_initialized_cache["initialized"] = True
            except Exception:
                try:
                    _db.init_db()
                    _db_initialized_cache["initialized"] = True
                except Exception:
                    logger.debug("数据库初始化失败，将在请求时重试", exc_info=True)

    with _db.get_db_connection() as (conn, c):
        sql_raw = (
            "SELECT * FROM users WHERE LOWER(username) = LOWER(%s) "
            "OR LOWER(email) = LOWER(%s) LIMIT 1"
        )
        sql = _db._safe_adapt_sql(sql_raw, conn)
        user = _db._safe_execute_fetchone(c, sql, (identifier, identifier), conn)

        if user:
            stored_password = user[2]

            if _db.verify_password(password, stored_password):
                if not _db.is_bcrypt_hash(stored_password):
                    _db.upgrade_user_password_to_bcrypt(user[0], password)

                cols = _db._get_table_columns(c, "users")
                has_user_type = "user_type" in cols

                result = {
                    "id": user[0],
                    "username": user[1],
                    "password": user[2],
                    "role": user[3],
                    "email": user[4],
                }

                if has_user_type and len(user) > 6:
                    result["user_type"] = user[6]
                else:
                    result["user_type"] = "free"

                return result

        return None


def upgrade_user_password_to_bcrypt(user_id, password):
    with _db.get_db_connection() as (conn, c):
        new_hashed_password = _db.hash_password(password)
        sql_raw = "UPDATE users SET password = ? WHERE id = ?"
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (new_hashed_password, user_id))
        conn.commit()


def update_user_password(user_id, current_password, new_password):
    import bcrypt

    with _db.get_db_connection() as (conn, c):
        sql = "SELECT password FROM users WHERE id = ?"
        user = _db._safe_execute_fetchone(c, sql, (user_id,), conn)

        if not user:
            return False

        current_password_bytes = current_password.encode("utf-8")
        stored_password = user["password"] if isinstance(user, dict) else user[0]

        if isinstance(stored_password, bytes):
            stored_password = stored_password.decode("utf-8")
        elif not isinstance(stored_password, str):
            stored_password = str(stored_password or "")

        if stored_password.startswith("$2b$"):
            if not bcrypt.checkpw(
                current_password_bytes, stored_password.encode("utf-8")
            ):
                return False
        else:
            import hashlib

            if hashlib.sha256(current_password_bytes).hexdigest() != stored_password:
                return False

        new_password_bytes = new_password.encode("utf-8")
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(new_password_bytes, salt).decode("utf-8")
        sql = _db._safe_adapt_sql("UPDATE users SET password = ? WHERE id = ?", conn)
        c.execute(sql, (hashed_password, user_id))
        conn.commit()
        return True


def _delete_user_related_data(conn, c, user_id, username, placeholder):
    sql_raw = f"DELETE FROM products WHERE user_id = {placeholder}"
    sql = _db._safe_adapt_sql(sql_raw, conn)
    c.execute(sql, (user_id,))

    sql_raw = f"DELETE FROM active_sessions WHERE user_id = {placeholder}"
    sql = _db._safe_adapt_sql(sql_raw, conn)
    c.execute(sql, (user_id,))

    sql_raw = f"DELETE FROM login_attempts WHERE identifier = {placeholder}"
    sql = _db._safe_adapt_sql(sql_raw, conn)
    c.execute(sql, (username,))

    sql_raw = f"DELETE FROM user_lockouts WHERE identifier = {placeholder}"
    sql = _db._safe_adapt_sql(sql_raw, conn)
    c.execute(sql, (username,))


def _delete_user_logs(conn, c, user_id, placeholder):
    try:
        sql_raw = f"DELETE FROM user_login_log WHERE user_id = {placeholder}"
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
    except Exception:
        logger.debug("登录日志表不存在，跳过", exc_info=True)

    try:
        sql_raw = f"DELETE FROM user_behavior_log WHERE user_id = {placeholder}"
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
    except Exception:
        logger.debug("行为日志表不存在，跳过", exc_info=True)

    sql_raw = f"DELETE FROM logistics WHERE user_id = {placeholder}"
    sql = _db._safe_adapt_sql(sql_raw, conn)
    c.execute(sql, (user_id,))


def _delete_user_extended(conn, c, user_id, placeholder):
    try:
        sql_raw = (
            f"DELETE FROM subscription_upgrade_history WHERE user_id = {placeholder}"
        )
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
    except Exception:
        logger.debug("升级历史表不存在，跳过", exc_info=True)

    sql_raw = f"DELETE FROM payment_orders WHERE user_id = {placeholder}"
    sql = _db._safe_adapt_sql(sql_raw, conn)
    c.execute(sql, (user_id,))

    try:
        sql_raw = (
            f"DELETE FROM admin_action_log "
            f"WHERE admin_id = {placeholder} "
            f"OR target_user_id = {placeholder}"
        )
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id, user_id))
    except Exception:
        logger.debug("管理员操作日志表不存在，跳过", exc_info=True)

    try:
        sql_raw = (
            f"UPDATE alert_records SET handled_by = NULL "
            f"WHERE handled_by = {placeholder}"
        )
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
    except Exception:
        logger.debug("告警记录表不存在，跳过", exc_info=True)


def delete_user(user_id):
    with _db.get_db_connection() as (conn, c):
        try:
            sql = "SELECT id, username, role FROM users WHERE id = ?"
            user = _db._safe_execute_fetchone(c, sql, (user_id,), conn)

            if not user:
                print(f"删除失败: 用户 ID={user_id} 不存在")
                return False

            print(f"准备删除用户: ID={user[0]}, 用户名={user[1]}, 角色={user[2]}")

            if user[2] == "admin":
                print(f"删除失败: 用户 {user[1]} 是管理员，不允许删除")
                return False

            placeholder = _db.get_placeholder()
            _delete_user_related_data(conn, c, user_id, user[1], placeholder)
            _delete_user_logs(conn, c, user_id, placeholder)
            _delete_user_extended(conn, c, user_id, placeholder)

            sql_raw = f"DELETE FROM users WHERE id = {placeholder}"
            sql = _db._safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))

            conn.commit()
            print(f"✅ 成功删除用户 {user[1]} (ID={user_id})")
            return True

        except Exception as e:
            logger.warning("删除用户失败: %s", e, exc_info=True)
            import traceback

            traceback.print_exc()
            conn.rollback()
            return False


def get_user_preferred_mode(user_id):
    with _db.get_db_connection() as (conn, c):
        if c is None:
            return None
        sql_raw = "SELECT preferred_mode FROM users WHERE id = ?"
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
        result = c.fetchone()

        if not result:
            return None

        if isinstance(result, (list, tuple)):
            return result[0]
        if isinstance(result, dict):
            return result.get("preferred_mode")
        if hasattr(result, "keys"):
            row_dict = dict(cast(Mapping[str, Any], result))
            return row_dict.get("preferred_mode")
        return cast(Optional[str], result)


def update_user_preferred_mode(user_id, mode):
    with _db.get_db_connection() as (conn, c):
        sql = _db._safe_adapt_sql(
            "UPDATE users SET preferred_mode = ? WHERE id = ?", conn
        )
        c.execute(sql, (mode, user_id))
        conn.commit()


def migrate_user_preferences():
    with _db.get_db_connection() as (conn, c):
        try:
            columns = _db._get_table_columns(c, "users")

            if "preferred_mode" not in columns:
                c.execute(
                    "ALTER TABLE users ADD COLUMN preferred_mode TEXT DEFAULT 'fast'"
                )
                conn.commit()
                print("已为users表添加preferred_mode列")

            c.execute("SELECT COUNT(*) FROM users WHERE preferred_mode IS NULL")
            null_count = c.fetchone()[0]

            if null_count > 0:
                c.execute(
                    "UPDATE users SET preferred_mode = 'fast' "
                    "WHERE preferred_mode IS NULL"
                )
                conn.commit()
                print(f"已为 {null_count} 个用户设置默认模式偏好")

        except (Exception,) as e:
            logger.warning("迁移用户偏好失败: %s", e)
            conn.rollback()
