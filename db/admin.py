import logging
import secrets
import string
from datetime import date

from db._proxy import _db
from db.admin_helpers import (
    _build_users_filter,
    _format_audit_log_rows,
    _format_user_row,
    _get_users_query,
)

logger = logging.getLogger(__name__)


def authenticate_admin(username, password):
    with _db.get_db_connection() as (conn, c):
        sql = _db._safe_adapt_sql(
            "SELECT id, username, password, role, email "
            "FROM users WHERE username = ? AND role = 'admin'",
            conn,
        )
        c.execute(sql, (username,))
        result = c.fetchone()

        if result:
            admin_id, uname, password_hash, role, email = result
            import bcrypt

            if bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")):
                if _db._is_postgresql_connection(conn):
                    update_sql = _db._safe_adapt_sql(
                        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                        conn,
                    )
                else:
                    update_sql = _db._safe_adapt_sql(
                        "UPDATE users SET last_login = datetime('now') WHERE id = ?",
                        conn,
                    )
                c.execute(update_sql, (admin_id,))
                conn.commit()
                return {
                    "id": admin_id,
                    "username": uname,
                    "role": role,
                    "email": email,
                }
        return None


def get_all_users(
    page=1,
    per_page=20,
    search=None,
    user_type_filter=None,
    status_filter=None,
):
    with _db.get_db_connection() as (conn, c):
        where_clause, safe_params = _build_users_filter(
            search, user_type_filter, status_filter
        )

        count_query = _db._safe_adapt_sql(
            f"SELECT COUNT(*) FROM users WHERE {where_clause}", conn
        )
        c.execute(count_query, safe_params)
        total_count = c.fetchone()[0]

        offset = (page - 1) * per_page
        cols = _db._get_table_columns(c, "users")
        has_logistics_limit = "logistics_templates_limit" in cols

        query = _db._safe_adapt_sql(
            _get_users_query(where_clause, has_logistics_limit), conn
        )
        c.execute(query, safe_params + [per_page, offset])
        users = c.fetchall()

        user_logistics_counts = {}
        for user in users:
            uid = user[0]
            sql = _db._safe_adapt_sql(
                "SELECT COUNT(*) FROM logistics WHERE user_id = ?", conn
            )
            c.execute(sql, (uid,))
            user_logistics_counts[uid] = c.fetchone()[0]

        formatted_users = [_format_user_row(u, user_logistics_counts) for u in users]

        return {
            "users": formatted_users,
            "total_count": total_count,
            "total_pages": (total_count + per_page - 1) // per_page,
            "current_page": page,
        }


def get_user_detail(user_id):
    with _db.get_db_connection() as (conn, c):
        sql = _db._safe_adapt_sql(
            "SELECT id, username, email, role, user_type, "
            "subscription_start, subscription_expires, "
            "remaining_calculations, logistics_templates_limit, "
            "is_auto_renew, created_at, last_login, "
            "is_frozen FROM users WHERE id = ?",
            conn,
        )
        c.execute(sql, (user_id,))
        user = c.fetchone()

        if not user:
            return None

        (
            uid,
            username,
            email,
            role,
            user_type,
            subscription_start,
            subscription_expires_raw,
            remaining_calculations,
            logistics_templates_limit,
            is_auto_renew,
            created_at,
            last_login,
            is_frozen,
        ) = user

        sql = _db._safe_adapt_sql(
            "SELECT COUNT(*) FROM logistics WHERE user_id = ?", conn
        )
        c.execute(sql, (uid,))
        logistics_count = c.fetchone()[0]

        sql = _db._safe_adapt_sql(
            "SELECT COUNT(*) FROM products WHERE user_id = ?", conn
        )
        c.execute(sql, (uid,))
        products_count = c.fetchone()[0]

        remaining_days = None
        subscription_end_iso = None
        expiry_dt = _db._subscription_expires_to_datetime(subscription_expires_raw)
        if expiry_dt is not None:
            subscription_end_iso = expiry_dt.isoformat()
            today = date.today()
            remaining_days = (expiry_dt.date() - today).days

        return {
            "id": uid,
            "username": username,
            "email": email,
            "role": role,
            "user_type": user_type,
            "subscription_start": subscription_start,
            "subscription_end": subscription_end_iso,
            "remaining_days": remaining_days,
            "remaining_calculations": remaining_calculations,
            "logistics_templates_limit": logistics_templates_limit,
            "current_logistics_count": logistics_count,
            "products_count": products_count,
            "is_auto_renew": is_auto_renew,
            "created_at": created_at,
            "last_login": last_login,
            "is_frozen": is_frozen,
        }


def _build_subscription_update(updates):
    set_clauses = []
    values = []
    for field, value in updates.items():
        if field == "subscription_end":
            serialized = _db._serialize_subscription_expires(value)
            set_clauses.append("subscription_expires = ?")
            values.append(serialized)
            continue
        if field in [
            "user_type",
            "subscription_start",
            "remaining_calculations",
            "logistics_templates_limit",
            "is_auto_renew",
            "is_frozen",
        ]:
            set_clauses.append(f"{field} = ?")
            values.append(value)
    return set_clauses, values


def update_user_subscription_admin(user_id, updates, admin_id):
    with _db.get_db_connection() as (conn, c):
        set_clauses, values = _build_subscription_update(updates)

        if not set_clauses:
            return False

        values.append(user_id)
        placeholder = _db.get_placeholder()
        query = _db.adapt_sql(
            f"UPDATE users SET {', '.join(set_clauses)} WHERE id = {placeholder}"
        )
        c.execute(query, values)

        if c.rowcount > 0:
            details_pairs = [f"{k}={v}" for k, v in updates.items()]
            action_details = "管理员更新用户订阅: " + ", ".join(details_pairs)
            sql = _db._safe_adapt_sql(
                "INSERT INTO audit_logs (admin_id, user_id, action, details)"
                " VALUES (?, ?, ?, ?)",
                conn,
            )
            c.execute(
                sql,
                (admin_id, user_id, "update_subscription", action_details),
            )
            conn.commit()
            try:
                _db.log_admin_action(
                    admin_id=admin_id,
                    action_type="更新订阅",
                    action_detail=action_details,
                    target_user_id=user_id,
                    target_type="subscription",
                )
            except Exception as e:
                logger.warning("记录管理员操作日志失败: %s", e)
            return True

        return False


def _detect_is_pg(conn):
    try:
        import psycopg2

        return isinstance(conn, psycopg2.extensions.connection)
    except (ImportError, AttributeError):
        return False


def freeze_user(user_id, admin_id):
    with _db.get_db_connection() as (conn, c):
        if _detect_is_pg(conn):
            sql = _db._safe_adapt_sql(
                "UPDATE users SET is_frozen = TRUE WHERE id = ?", conn
            )
        else:
            sql = _db._safe_adapt_sql(
                "UPDATE users SET is_frozen = 1 WHERE id = ?", conn
            )
        c.execute(sql, (user_id,))

        if c.rowcount > 0:
            sql = _db._safe_adapt_sql(
                "INSERT INTO audit_logs (admin_id, user_id, action, details)"
                " VALUES (?, ?, ?, ?)",
                conn,
            )
            c.execute(sql, (admin_id, user_id, "freeze_user", "管理员冻结用户"))
            conn.commit()
            try:
                _db.log_admin_action(
                    admin_id=admin_id,
                    action_type="冻结用户",
                    action_detail=f"管理员冻结了用户ID: {user_id}",
                    target_user_id=user_id,
                    target_type="user",
                )
            except Exception as e:
                logger.warning("记录管理员操作日志失败: %s", e)
            return True

        return False


def unfreeze_user(user_id, admin_id):
    with _db.get_db_connection() as (conn, c):
        if _detect_is_pg(conn):
            sql = _db._safe_adapt_sql(
                "UPDATE users SET is_frozen = FALSE WHERE id = ?", conn
            )
        else:
            sql = _db._safe_adapt_sql(
                "UPDATE users SET is_frozen = 0 WHERE id = ?", conn
            )
        c.execute(sql, (user_id,))

        if c.rowcount > 0:
            sql = _db._safe_adapt_sql(
                "INSERT INTO audit_logs (admin_id, user_id, action, details)"
                " VALUES (?, ?, ?, ?)",
                conn,
            )
            c.execute(sql, (admin_id, user_id, "unfreeze_user", "管理员解冻用户"))
            conn.commit()
            try:
                _db.log_admin_action(
                    admin_id=admin_id,
                    action_type="解冻用户",
                    action_detail=f"管理员解冻了用户ID: {user_id}",
                    target_user_id=user_id,
                    target_type="user",
                )
            except Exception as e:
                logger.warning("记录管理员操作日志失败: %s", e)
            return True

        return False


def delete_user_admin(user_id, admin_id):
    with _db.get_db_connection() as (conn, c):
        user_role_sql = _db._safe_adapt_sql(
            "SELECT role, username FROM users WHERE id = ?", conn
        )
        user_role_row = _db._safe_execute_fetchone(c, user_role_sql, (user_id,))
        if user_role_row and user_role_row[0] == "admin":
            print("删除失败: 不允许删除管理员账号及其数据")
            return False

        user_sql = _db._safe_adapt_sql("SELECT username FROM users WHERE id = ?", conn)
        user = _db._safe_execute_fetchone(c, user_sql, (user_id,))
        username = user[0] if user else f"ID:{user_id}"

        c.execute(
            _db._safe_adapt_sql("DELETE FROM logistics WHERE user_id = ?", conn),
            (user_id,),
        )
        c.execute(
            _db._safe_adapt_sql("DELETE FROM products WHERE user_id = ?", conn),
            (user_id,),
        )
        c.execute(
            _db._safe_adapt_sql("DELETE FROM users WHERE id = ?", conn),
            (user_id,),
        )

        if c.rowcount > 0:
            conn.commit()
            try:
                _db.log_admin_action(
                    admin_id=admin_id,
                    action_type="删除用户",
                    action_detail=(f"管理员删除了用户: {username} (ID: {user_id})"),
                    target_user_id=None,
                    target_type="user",
                )
            except Exception as e:
                logger.warning("记录管理员操作日志失败: %s", e)
            return True

        return False


def batch_update_users(user_ids, updates, admin_id):
    with _db.get_db_connection() as (conn, c):
        success_count = 0

        for uid in user_ids:
            set_clauses, values = _build_subscription_update(updates)

            if set_clauses:
                values.append(uid)
                placeholder = _db.get_placeholder()
                query = _db.adapt_sql(
                    f"UPDATE users SET {', '.join(set_clauses)}"
                    f" WHERE id = {placeholder}"
                )
                c.execute(query, values)

                if c.rowcount > 0:
                    success_count += 1
                    details_pairs = [f"{k}={v}" for k, v in updates.items()]
                    action_details = "批量更新: " + ", ".join(details_pairs)
                    sql = _db._safe_adapt_sql(
                        "INSERT INTO audit_logs"
                        " (admin_id, user_id, action, details)"
                        " VALUES (?, ?, ?, ?)",
                        conn,
                    )
                    c.execute(
                        sql,
                        (admin_id, uid, "batch_update", action_details),
                    )

        conn.commit()
        return success_count


def get_audit_logs(
    page=1,
    per_page=50,
    admin_id=None,
    user_id=None,
    action=None,
):
    with _db.get_db_connection() as (_, c):
        from sql_security import build_where_clause

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

        where_clause, safe_params = build_where_clause(where_conditions, params)

        count_query = f"SELECT COUNT(*) FROM audit_logs WHERE {where_clause}"
        c.execute(count_query, safe_params)
        total_count = c.fetchone()[0]

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
        c.execute(query, safe_params + [per_page, offset])
        logs = c.fetchall()

        formatted_logs = _format_audit_log_rows(logs)

        return {
            "logs": formatted_logs,
            "total_count": total_count,
            "total_pages": (total_count + per_page - 1) // per_page,
            "current_page": page,
        }


def reset_user_password(user_id, admin_id):
    alphabet = string.ascii_letters + string.digits
    new_password = "".join(secrets.choice(alphabet) for _ in range(12))

    import bcrypt

    password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())

    with _db.get_db_connection() as (conn, c):
        c.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (password_hash.decode("utf-8"), user_id),
        )

        if c.rowcount > 0:
            details_text = f"管理员重置密码: {new_password}"
            c.execute(
                "INSERT INTO audit_logs (admin_id, user_id, action, details)"
                " VALUES (?, ?, ?, ?)",
                (admin_id, user_id, "reset_password", details_text),
            )
            conn.commit()
            try:
                _db.log_admin_action(
                    admin_id=admin_id,
                    action_type="重置密码",
                    action_detail=(f"管理员重置了用户ID: {user_id} 的密码"),
                    target_user_id=user_id,
                    target_type="user",
                )
            except Exception as e:
                logger.warning("记录管理员操作日志失败: %s", e)
            return new_password

        return None
