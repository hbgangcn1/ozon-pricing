import logging
import time
from typing import Optional

from db._proxy import _db
from db.helpers import DB_EXCEPTIONS

logger = logging.getLogger(__name__)


def log_user_login(
    user_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> bool:
    """记录用户登录日志"""
    with _db.get_db_connection() as (conn, c):
        try:
            device_type = "unknown"
            if user_agent:
                ua_lower = user_agent.lower()
                if "mobile" in ua_lower or "android" in ua_lower:
                    device_type = "mobile"
                elif "tablet" in ua_lower or "ipad" in ua_lower:
                    device_type = "tablet"
                else:
                    device_type = "desktop"

            login_time = int(time.time())
            sql_raw = (
                "INSERT INTO user_login_log"
                " (user_id, login_time, ip_address, user_agent, device_type)"
                " VALUES (?, ?, ?, ?, ?)"
            )
            sql = _db._safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id, login_time, ip_address, user_agent, device_type))

            sql_raw = "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?"
            sql = _db._safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id,))

            conn.commit()
            return True
        except Exception as e:
            error_str = str(e).lower()
            if "duplicate" in error_str or "unique" in error_str:
                try:
                    sql_raw = (
                        "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?"
                    )
                    sql = _db._safe_adapt_sql(sql_raw, conn)
                    c.execute(sql, (user_id,))
                    conn.commit()
                except DB_EXCEPTIONS:
                    pass
                return True
            logger.warning("记录用户登录日志失败: %s", e)
            return False


def log_user_behavior(
    user_id: int,
    behavior_type: str,
    behavior_detail: Optional[str] = None,
    calculation_mode: Optional[str] = None,
) -> bool:
    """记录用户行为日志"""
    with _db.get_db_connection() as (conn, c):
        try:
            sql_raw = (
                "INSERT INTO user_behavior_log"
                " (user_id, behavior_type, behavior_detail, calculation_mode)"
                " VALUES (?, ?, ?, ?)"
            )
            sql = _db._safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (user_id, behavior_type, behavior_detail, calculation_mode))
            conn.commit()
            return True
        except Exception as e:
            logger.warning("记录用户行为日志失败: %s", e)
            return False


def log_admin_action(
    admin_id: int,
    action_type: str,
    action_detail: str,
    target_user_id: Optional[int] = None,
    target_type: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> bool:
    """记录管理员操作日志"""
    with _db.get_db_connection() as (conn, c):
        try:
            sql_raw = (
                "INSERT INTO admin_action_log"
                " (admin_id, action_type, action_detail, target_user_id,"
                " target_type, ip_address)"
                " VALUES (?, ?, ?, ?, ?, ?)"
            )
            sql = _db._safe_adapt_sql(sql_raw, conn)
            c.execute(
                sql,
                (
                    admin_id,
                    action_type,
                    action_detail,
                    target_user_id,
                    target_type,
                    ip_address,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("记录管理员操作日志失败: %s", e)
            return False


def create_alert(
    alert_type: str,
    alert_level: str,
    description: str,
    threshold_value: Optional[float] = None,
    actual_value: Optional[float] = None,
) -> bool:
    """创建异常告警记录"""
    with _db.get_db_connection() as (conn, c):
        try:
            c.execute(
                "INSERT INTO alert_records"
                " (alert_type, alert_level, description,"
                " threshold_value, actual_value)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    alert_type,
                    alert_level,
                    description,
                    threshold_value,
                    actual_value,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("创建告警记录失败: %s", e)
            return False
