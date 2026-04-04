import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from db._proxy import _db

logger = logging.getLogger(__name__)


def get_statistics_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """获取统计缓存数据"""
    with _db.get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            sql_raw = (
                "SELECT cache_data FROM statistics_cache"
                " WHERE cache_key = ? AND expires_at > ?"
            )
            sql = _db._safe_adapt_sql(sql_raw, conn)
            result = _db._safe_execute_fetchone(c, sql, (cache_key, current_time), conn)
            if result:
                return json.loads(result[0])
            return None
        except Exception as e:
            logger.warning("获取缓存失败: %s", e)
            return None


def _convert_decimal_to_float(obj):
    """递归转换Decimal为float，用于JSON序列化"""
    from decimal import Decimal

    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _convert_decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimal_to_float(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(_convert_decimal_to_float(item) for item in obj)
    return obj


def set_statistics_cache(
    cache_key: str, cache_data: Dict[str, Any], ttl: int = 300
) -> bool:
    """设置统计缓存数据（ttl秒，默认5分钟）"""
    with _db.get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            expires_at = current_time + ttl
            cache_data_serializable = _convert_decimal_to_float(cache_data)
            cache_json = json.dumps(cache_data_serializable, ensure_ascii=False)

            if _db._is_postgresql_connection(conn):
                sql = (
                    "INSERT INTO statistics_cache"
                    " (cache_key, cache_data, expires_at, updated_at)"
                    " VALUES (%s, %s, %s, %s)"
                    " ON CONFLICT (cache_key) DO UPDATE SET"
                    " cache_data = EXCLUDED.cache_data,"
                    " expires_at = EXCLUDED.expires_at,"
                    " updated_at = EXCLUDED.updated_at"
                )
            else:
                sql = (
                    "INSERT OR REPLACE INTO statistics_cache"
                    " (cache_key, cache_data, expires_at, updated_at)"
                    " VALUES (?, ?, ?, ?)"
                )
            c.execute(sql, (cache_key, cache_json, expires_at, current_time))
            conn.commit()
            return True
        except Exception as e:
            logger.warning("设置缓存失败: %s", e)
            return False


def clear_expired_cache() -> int:
    """清理过期的缓存数据"""
    with _db.get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            c.execute(
                "DELETE FROM statistics_cache WHERE expires_at < ?",
                (current_time,),
            )
            conn.commit()
            return c.rowcount
        except Exception as e:
            logger.warning("清理缓存失败: %s", e)
            return 0


def clear_all_statistics_cache() -> int:
    """清除所有统计缓存数据"""
    with _db.get_db_connection() as (conn, c):
        try:
            sql = _db._safe_adapt_sql("DELETE FROM statistics_cache", conn)
            c.execute(sql)
            conn.commit()
            return c.rowcount
        except Exception as e:
            logger.warning("清除所有缓存失败: %s", e)
            return 0


def _get_user_stats(c, conn, current_time, today_start):
    """查询用户统计数据：今日活跃、今日新增、总数"""
    sql = _db._safe_adapt_sql(
        "SELECT COUNT(DISTINCT user_id) FROM user_login_log WHERE login_time >= ?",
        conn,
    )
    c.execute(sql, (today_start,))
    active_users_today = c.fetchone()[0]

    if _db._is_postgresql_connection(conn):
        safe_user_expr = _db._build_safe_timestamp_expr("created_at")
        sql = f"""
            WITH normalized_users AS (
                SELECT {safe_user_expr} AS created_ts, role FROM users
            )
            SELECT COUNT(*) FROM normalized_users
            WHERE role != 'admin' AND created_ts >= to_timestamp(%s)
        """
        c.execute(sql, (today_start,))
    else:
        today_start_str = datetime.fromtimestamp(today_start).strftime(
            "%Y-%m-%d 00:00:00"
        )
        c.execute(
            "SELECT COUNT(*) FROM users WHERE created_at >= ?",
            (today_start_str,),
        )
    new_users_today = c.fetchone()[0]

    sql = _db._safe_adapt_sql("SELECT COUNT(*) FROM users WHERE role != 'admin'", conn)
    c.execute(sql)
    total_users = c.fetchone()[0]

    return active_users_today, new_users_today, total_users


def _get_revenue_stats(c, conn, today_start, yesterday_start, month_start):
    """查询收入统计：总收入、今日、昨日、本月"""
    sql = _db._safe_adapt_sql(
        "SELECT COALESCE(SUM(amount), 0) / 100.0"
        " FROM payment_orders WHERE status = 'SUCCESS'",
        conn,
    )
    c.execute(sql)
    total_revenue = c.fetchone()[0]

    orders_cte = ""
    if _db._is_postgresql_connection(conn):
        safe_order_expr = _db._build_safe_timestamp_expr("created_at")
        orders_cte = f"""
            WITH normalized_orders AS (
                SELECT amount, status,
                    {safe_order_expr} AS created_ts
                FROM payment_orders
            )
        """
        c.execute(
            orders_cte + "SELECT COALESCE(SUM(amount), 0) / 100.0"
            " FROM normalized_orders"
            " WHERE status = 'SUCCESS'"
            " AND created_ts >= to_timestamp(%s)",
            (today_start,),
        )
        revenue_today = c.fetchone()[0]
        c.execute(
            orders_cte + "SELECT COALESCE(SUM(amount), 0) / 100.0"
            " FROM normalized_orders"
            " WHERE status = 'SUCCESS'"
            " AND created_ts >= to_timestamp(%s)"
            " AND created_ts < to_timestamp(%s)",
            (yesterday_start, today_start),
        )
        revenue_yesterday = c.fetchone()[0]
        c.execute(
            orders_cte + "SELECT COALESCE(SUM(amount), 0) / 100.0"
            " FROM normalized_orders"
            " WHERE status = 'SUCCESS'"
            " AND created_ts >= to_timestamp(%s)",
            (month_start,),
        )
        revenue_month = c.fetchone()[0]
    else:
        sql = _db._safe_adapt_sql(
            "SELECT COALESCE(SUM(amount), 0) / 100.0"
            " FROM payment_orders"
            " WHERE status = 'SUCCESS' AND created_at >= ?",
            conn,
        )
        c.execute(sql, (today_start,))
        revenue_today = c.fetchone()[0]
        sql = _db._safe_adapt_sql(
            "SELECT COALESCE(SUM(amount), 0) / 100.0"
            " FROM payment_orders"
            " WHERE status = 'SUCCESS'"
            " AND created_at >= ? AND created_at < ?",
            conn,
        )
        c.execute(sql, (yesterday_start, today_start))
        revenue_yesterday = c.fetchone()[0]
        sql = _db._safe_adapt_sql(
            "SELECT COALESCE(SUM(amount), 0) / 100.0"
            " FROM payment_orders"
            " WHERE status = 'SUCCESS' AND created_at >= ?",
            conn,
        )
        c.execute(sql, (month_start,))
        revenue_month = c.fetchone()[0]

    return total_revenue, revenue_today, revenue_yesterday, revenue_month


def get_dashboard_stats() -> Dict[str, Any]:
    """获取总览看板数据"""
    cache_key = "dashboard_stats"
    cached = _db.get_statistics_cache(cache_key)
    if cached:
        return cached

    with _db.get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            today_start = current_time - (current_time % 86400)
            yesterday_start = today_start - 86400
            month_start = current_time - (current_time % (30 * 86400))

            active_users_today, new_users_today, total_users = _get_user_stats(
                c, conn, current_time, today_start
            )

            total_revenue, revenue_today, revenue_yesterday, revenue_month = (
                _get_revenue_stats(c, conn, today_start, yesterday_start, month_start)
            )

            sql = _db._safe_adapt_sql(
                "SELECT COUNT(DISTINCT user_id) FROM user_login_log"
                " WHERE login_time >= ?",
                conn,
            )
            c.execute(sql, (current_time - 300,))
            online_users = c.fetchone()[0]

            result = {
                "active_users_today": active_users_today,
                "new_users_today": new_users_today,
                "total_users": total_users,
                "total_revenue": round(total_revenue, 2),
                "revenue_today": round(revenue_today, 2),
                "revenue_yesterday": round(revenue_yesterday, 2),
                "revenue_month": round(revenue_month, 2),
                "online_users": online_users,
                "timestamp": current_time,
            }

            _db.set_statistics_cache(cache_key, result, 300)
            return result
        except Exception as e:
            logger.warning("获取总览数据失败: %s", e)
            return {}
