"""
统计与运营看板数据服务
提供各类统计数据查询和分析功能
"""

import time
import sqlite3
import streamlit as st
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any

try:
    from .db_utils import (
        get_db_connection, get_statistics_cache, set_statistics_cache
    )
    from .intelligent_cache_manager import cache_result, get_cache_stats
except ImportError:
    from db_utils import (
        get_db_connection, get_statistics_cache, set_statistics_cache
    )
    try:
        from intelligent_cache_manager import cache_result, get_cache_stats
    except ImportError:
        # 如果智能缓存不可用，使用简单的缓存装饰器
        def cache_result(category='default', ttl=None):
            # 参数保留用于接口一致性，fallback实现不使用这些参数
            _ = category, ttl  # 明确使用参数以消除警告

            def decorator(func):
                return func
            return decorator

        def get_cache_stats():
            return {'status': 'unavailable'}


@cache_result('statistics', ttl=600)  # 智能缓存10分钟
@st.cache_data(ttl=600)  # 缓存10分钟，留存分析计算复杂
def get_retention_analysis(start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> Dict[str, Any]:
    """获取留存分析数据

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
    """
    cache_key = f"retention_analysis_{start_date}_{end_date}"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            # 如果未指定日期范围，默认最近30天
            if not end_date:
                end_date = date.today().isoformat()
            if not start_date:
                start_date = (date.today() - timedelta(days=30)).isoformat()

            # 转换为时间戳
            end_timestamp = int(
                datetime.fromisoformat(end_date).timestamp())
            start_timestamp = int(
                datetime.fromisoformat(start_date).timestamp())

            # 获取每日注册用户及留存情况
            daily_retention = []

            current = start_timestamp
            while current <= end_timestamp:
                day_start = current
                day_end = current + 86400

                # 获取该日注册的用户
                registered_users = c.execute("""
                    SELECT id FROM users
                    WHERE created_at >= datetime(?, 'unixepoch')
                    AND created_at < datetime(?, 'unixepoch')
                    AND role != 'admin'
                """, (day_start, day_end)).fetchall()

                if registered_users:
                    user_ids = [u[0] for u in registered_users]
                    total_registered = len(user_ids)

                    # 计算D1留存（第二天登录的用户数）
                    d1_start = day_end
                    d1_end = d1_start + 86400
                    d1_retained = c.execute(f"""
                        SELECT COUNT(DISTINCT user_id) FROM user_login_log
                        WHERE user_id IN ({','.join('?' * len(user_ids))})
                        AND login_time >= ? AND login_time < ?
                    """, user_ids + [d1_start, d1_end]).fetchone()[0]

                    # 计算D3留存
                    d3_start = day_end + 2 * 86400
                    d3_end = d3_start + 86400
                    d3_retained = c.execute(f"""
                        SELECT COUNT(DISTINCT user_id) FROM user_login_log
                        WHERE user_id IN ({','.join('?' * len(user_ids))})
                        AND login_time >= ? AND login_time < ?
                    """, user_ids + [d3_start, d3_end]).fetchone()[0]

                    # 计算D7留存
                    d7_start = day_end + 6 * 86400
                    d7_end = d7_start + 86400
                    d7_retained = c.execute(f"""
                        SELECT COUNT(DISTINCT user_id) FROM user_login_log
                        WHERE user_id IN ({','.join('?' * len(user_ids))})
                        AND login_time >= ? AND login_time < ?
                    """, user_ids + [d7_start, d7_end]).fetchone()[0]

                    # 计算D30留存
                    d30_start = day_end + 29 * 86400
                    d30_end = d30_start + 86400
                    d30_retained = c.execute(f"""
                        SELECT COUNT(DISTINCT user_id) FROM user_login_log
                        WHERE user_id IN ({','.join('?' * len(user_ids))})
                        AND login_time >= ? AND login_time < ?
                    """, user_ids + [d30_start, d30_end]).fetchone()[0]

                    date_str = datetime.fromtimestamp(day_start).strftime(
                        '%Y-%m-%d')
                    d1_pct = (round(d1_retained / total_registered * 100, 2)
                              if total_registered > 0 else 0)
                    d3_pct = (round(d3_retained / total_registered * 100, 2)
                              if total_registered > 0 else 0)
                    d7_pct = (round(d7_retained / total_registered * 100, 2)
                              if total_registered > 0 else 0)
                    d30_pct = (round(d30_retained / total_registered * 100, 2)
                               if total_registered > 0 else 0)

                    daily_retention.append({
                        'date': date_str,
                        'registered': total_registered,
                        'd1': d1_pct,
                        'd3': d3_pct,
                        'd7': d7_pct,
                        'd30': d30_pct,
                    })

                current += 86400

            # 计算平均留存率
            if daily_retention:
                count = len(daily_retention)
                avg_d1 = sum(d['d1'] for d in daily_retention) / count
                avg_d3 = sum(d['d3'] for d in daily_retention) / count
                avg_d7 = sum(d['d7'] for d in daily_retention) / count
                avg_d30 = sum(d['d30'] for d in daily_retention) / count
            else:
                avg_d1 = avg_d3 = avg_d7 = avg_d30 = 0

            result = {
                'd1_retention': round(avg_d1, 2),
                'd3_retention': round(avg_d3, 2),
                'd7_retention': round(avg_d7, 2),
                'd30_retention': round(avg_d30, 2),
                'daily_trend': daily_retention,
                'timestamp': int(time.time())
            }

            # 缓存5分钟
            set_statistics_cache(cache_key, result, 300)
            return result
        except Exception as e:
            print(f"获取留存分析数据失败: {e}")
            return {}


@cache_result('statistics', ttl=300)  # 智能缓存5分钟
@st.cache_data(ttl=300)  # 缓存5分钟
def get_user_activity_stats(start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> Dict[str, Any]:
    """获取用户活跃统计数据

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
    """
    cache_key = f"user_activity_{start_date}_{end_date}"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            # 如果未指定日期范围，默认最近30天
            if not end_date:
                end_date = date.today().isoformat()
            if not start_date:
                start_date = (date.today() - timedelta(days=30)).isoformat()

            end_timestamp = int(
                datetime.fromisoformat(end_date).timestamp())
            start_timestamp = int(
                datetime.fromisoformat(start_date).timestamp())

            # DAU（日活跃用户数）- 今天
            today_start = int(time.time()) - (int(time.time()) % 86400)
            dau = c.execute("""
                SELECT COUNT(DISTINCT user_id) FROM user_login_log
                WHERE login_time >= ?
            """, (today_start,)).fetchone()[0]

            # WAU（周活跃用户数）- 最近7天
            week_start = today_start - 7 * 86400
            wau = c.execute("""
                SELECT COUNT(DISTINCT user_id) FROM user_login_log
                WHERE login_time >= ?
            """, (week_start,)).fetchone()[0]

            # MAU（月活跃用户数）- 最近30天
            month_start = today_start - 30 * 86400
            mau = c.execute("""
                SELECT COUNT(DISTINCT user_id) FROM user_login_log
                WHERE login_time >= ?
            """, (month_start,)).fetchone()[0]

            # Top 10活跃用户
            top_users = c.execute("""
                SELECT
                    u.id, u.username, u.user_type,
                    COUNT(l.id) as login_count,
                    MAX(l.login_time) as last_login
                FROM users u
                INNER JOIN user_login_log l ON u.id = l.user_id
                WHERE l.login_time >= ? AND l.login_time <= ?
                GROUP BY u.id
                ORDER BY login_count DESC
                LIMIT 10
            """, (start_timestamp, end_timestamp)).fetchall()

            top_active_users = []
            for user in top_users:
                top_active_users.append({
                    'user_id': user[0],
                    'username': user[1],
                    'user_type': user[2],
                    'login_count': user[3],
                    'last_login': datetime.fromtimestamp(user[4]).strftime(
                        '%Y-%m-%d %H:%M:%S')
                })

            # 30天活跃趋势
            trend = []
            current = today_start - 30 * 86400
            while current <= today_start:
                day_start = current
                day_end = current + 86400

                active_count = c.execute("""
                    SELECT COUNT(DISTINCT user_id) FROM user_login_log
                    WHERE login_time >= ? AND login_time < ?
                """, (day_start, day_end)).fetchone()[0]

                date_str = datetime.fromtimestamp(day_start).strftime(
                    '%Y-%m-%d')
                trend.append({
                    'date': date_str,
                    'active_users': active_count
                })

                current += 86400

            result = {
                'dau': dau,
                'wau': wau,
                'mau': mau,
                'top_active_users': top_active_users,
                'trend': trend,
                'timestamp': int(time.time())
            }

            # 缓存5分钟
            set_statistics_cache(cache_key, result, 300)
            return result
        except Exception as e:
            print(f"获取用户活跃统计失败: {e}")
            return {}


@cache_result('statistics', ttl=300)  # 智能缓存5分钟
@st.cache_data(ttl=300)  # 缓存5分钟
def get_revenue_stats(start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> Dict[str, Any]:
    """获取充值与收入统计数据

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
    """
    cache_key = f"revenue_stats_{start_date}_{end_date}"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            # 如果未指定日期范围，默认最近30天
            if not end_date:
                end_date = date.today().isoformat()
            if not start_date:
                start_date = (date.today() - timedelta(days=30)).isoformat()

            end_timestamp = int(
                datetime.fromisoformat(end_date).timestamp())
            start_timestamp = int(
                datetime.fromisoformat(start_date).timestamp())

            # 订单列表
            orders = c.execute("""
                SELECT
                    o.order_id, o.user_id, u.username, o.description,
                    o.amount, o.status, o.created_at, o.duration
                FROM payment_orders o
                LEFT JOIN users u ON o.user_id = u.id
                WHERE o.created_at >= ? AND o.created_at <= ?
                ORDER BY o.created_at DESC
            """, (start_timestamp, end_timestamp)).fetchall()

            order_list = []
            for order in orders:
                order_list.append({
                    'order_id': order[0],
                    'user_id': order[1],
                    'username': order[2],
                    'plan_type': order[3],
                    'amount': order[4] / 100.0,  # 转换为元
                    'status': order[5],
                    'created_at': datetime.fromtimestamp(order[6]).strftime(
                        '%Y-%m-%d %H:%M:%S'),
                    'duration': order[7]
                })

            # 总订单数和总金额
            total_orders = len(order_list)
            success_list = [o for o in order_list
                            if o['status'] == 'SUCCESS']
            total_amount = sum(o['amount'] for o in success_list)

            # 平均客单价
            avg_order_value = (total_amount / len(success_list)
                               if success_list else 0)

            # 收入趋势图（按日）
            revenue_trend = []
            current = start_timestamp
            while current <= end_timestamp:
                day_start = current
                day_end = current + 86400

                daily_revenue = c.execute("""
                    SELECT COALESCE(SUM(amount), 0) / 100.0
                    FROM payment_orders
                    WHERE status = 'SUCCESS'
                    AND created_at >= ? AND created_at < ?
                """, (day_start, day_end)).fetchone()[0]

                date_str = datetime.fromtimestamp(day_start).strftime(
                    '%Y-%m-%d')
                revenue_trend.append({
                    'date': date_str,
                    'revenue': round(daily_revenue, 2)
                })

                current += 86400

            # 套餐分布占比
            plan_distribution = c.execute("""
                SELECT description, COUNT(*) as count,
                       SUM(amount) / 100.0 as total_amount
                FROM payment_orders
                WHERE status = 'SUCCESS'
                AND created_at >= ? AND created_at <= ?
                GROUP BY description
            """, (start_timestamp, end_timestamp)).fetchall()

            plan_stats = []
            for plan in plan_distribution:
                plan_stats.append({
                    'plan_type': plan[0],
                    'count': plan[1],
                    'total_amount': round(plan[2], 2)
                })

            result = {
                'total_orders': total_orders,
                'total_amount': round(total_amount, 2),
                'avg_order_value': round(avg_order_value, 2),
                'order_list': order_list,
                'revenue_trend': revenue_trend,
                'plan_distribution': plan_stats,
                'timestamp': int(time.time())
            }

            # 缓存5分钟
            set_statistics_cache(cache_key, result, 300)
            return result
        except Exception as e:
            print(f"获取收入统计失败: {e}")
            return {}


def get_user_retention_details(
        page: int = 1, per_page: int = 20,
        sort_by: str = 'login_count_desc') -> Dict[str, Any]:
    """获取用户留存明细

    Args:
        page: 页码
        per_page: 每页数量
        sort_by: 排序方式
    """
    with get_db_connection() as (conn, c):
        try:
            # 排序字段映射
            sort_map = {
                'login_count_desc': 'login_count DESC',
                'login_count_asc': 'login_count ASC',
                'created_at_desc': 'u.created_at DESC',
                'created_at_asc': 'u.created_at ASC',
                'last_login_desc': 'last_login_time DESC',
                'last_login_asc': 'last_login_time ASC',
            }
            order_clause = sort_map.get(sort_by, 'login_count DESC')

            # 获取总数
            total_count = c.execute("""
                SELECT COUNT(*) FROM users WHERE role != 'admin'
            """).fetchone()[0]

            # 获取分页数据
            offset = (page - 1) * per_page
            users = c.execute(f"""
                SELECT
                    u.id, u.username, u.email, u.user_type,
                    u.created_at, u.last_login,
                    u.subscription_end, u.remaining_calculations,
                    COUNT(l.id) as login_count,
                    MIN(l.login_time) as first_login_time,
                    MAX(l.login_time) as last_login_time
                FROM users u
                LEFT JOIN user_login_log l ON u.id = l.user_id
                WHERE u.role != 'admin'
                GROUP BY u.id
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
            """, (per_page, offset)).fetchall()

            user_details = []
            for user in users:
                # 计算留存天数
                created_at = user[4]
                if created_at:
                    try:
                        created_date = datetime.fromisoformat(created_at)
                        retention_days = (datetime.now() - created_date).days
                    except (ValueError, TypeError):
                        retention_days = 0
                else:
                    retention_days = 0

                # 检查是否续费
                subscription_end = user[6]
                is_renewed = False
                if subscription_end:
                    try:
                        end_date = datetime.fromisoformat(subscription_end)
                        is_renewed = end_date > datetime.now()
                    except (ValueError, TypeError):
                        pass

                user_details.append({
                    'user_id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'user_type': user[3],
                    'created_at': created_at,
                    'last_login': user[5],
                    'login_count': user[8],
                    'retention_days': retention_days,
                    'is_renewed': is_renewed,
                    'remaining_calculations': user[7]
                })

            return {
                'total': total_count,
                'users': user_details,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        except Exception as e:
            print(f"获取用户留存明细失败: {e}")
            return {}


def get_plan_stats(start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> Dict[str, Any]:
    """获取套餐统计数据

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
    """
    cache_key = f"plan_stats_{start_date}_{end_date}"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            # 各套餐用户数量
            plan_count = c.execute("""
                SELECT user_type, COUNT(*) as count
                FROM users
                WHERE role != 'admin'
                GROUP BY user_type
            """).fetchall()

            plan_count_stats = []
            for plan in plan_count:
                plan_count_stats.append({
                    'plan_type': plan[0],
                    'user_count': plan[1]
                })

            # 套餐升级路径统计
            upgrade_paths = c.execute("""
                SELECT from_plan, to_plan, COUNT(*) as count
                FROM subscription_upgrade_history
                GROUP BY from_plan, to_plan
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()

            upgrade_path_stats = []
            for path in upgrade_paths:
                upgrade_path_stats.append({
                    'from_plan': path[0],
                    'to_plan': path[1],
                    'count': path[2]
                })

            # 套餐收入贡献
            plan_revenue = c.execute("""
                SELECT description, SUM(amount) / 100.0 as revenue
                FROM payment_orders
                WHERE status = 'SUCCESS'
                GROUP BY description
                ORDER BY revenue DESC
            """).fetchall()

            plan_revenue_stats = []
            for revenue in plan_revenue:
                plan_revenue_stats.append({
                    'plan_type': revenue[0],
                    'total_revenue': round(revenue[1], 2)
                })

            # 用户生命周期价值（LTV）基础统计
            ltv_stats = c.execute("""
                SELECT
                    u.user_type,
                    COUNT(DISTINCT u.id) as user_count,
                    AVG(total.amount) as avg_revenue,
                    SUM(total.amount) / COUNT(DISTINCT u.id) as ltv
                FROM users u
                LEFT JOIN (
                    SELECT user_id, SUM(amount) / 100.0 as amount
                    FROM payment_orders
                    WHERE status = 'SUCCESS'
                    GROUP BY user_id
                ) total ON u.id = total.user_id
                WHERE u.role != 'admin'
                GROUP BY u.user_type
            """).fetchall()

            ltv_data = []
            for ltv in ltv_stats:
                ltv_data.append({
                    'user_type': ltv[0],
                    'user_count': ltv[1],
                    'avg_revenue': round(ltv[2] if ltv[2] else 0, 2),
                    'ltv': round(ltv[3] if ltv[3] else 0, 2)
                })

            result = {
                'plan_count': plan_count_stats,
                'upgrade_paths': upgrade_path_stats,
                'plan_revenue': plan_revenue_stats,
                'ltv_stats': ltv_data,
                'timestamp': int(time.time())
            }

            # 缓存5分钟
            set_statistics_cache(cache_key, result, 300)
            return result
        except Exception as e:
            print(f"获取套餐统计失败: {e}")
            return {}


def get_admin_action_logs(page: int = 1, per_page: int = 20) -> Dict[str, Any]:
    """获取管理员操作日志

    Args:
        page: 页码
        per_page: 每页数量
    """
    with get_db_connection() as (conn, c):
        try:
            # 获取总数
            total_count = c.execute("""
                SELECT COUNT(*) FROM admin_action_log
            """).fetchone()[0]

            # 获取分页数据
            offset = (page - 1) * per_page
            logs = c.execute("""
                SELECT
                    l.id, l.admin_id, l.action_type, l.action_detail,
                    l.target_user_id, l.created_at,
                    a.username as admin_username,
                    u.username as target_username
                FROM admin_action_log l
                LEFT JOIN admin_users a ON l.admin_id = a.id
                LEFT JOIN users u ON l.target_user_id = u.id
                ORDER BY l.created_at DESC
                LIMIT ? OFFSET ?
            """, (per_page, offset)).fetchall()

            log_list = []
            for log in logs:
                log_list.append({
                    'id': log[0],
                    'admin_id': log[1],
                    'admin_username': log[6],
                    'action_type': log[2],
                    'action_detail': log[3],
                    'target_user_id': log[4],
                    'target_username': log[7],
                    'created_at': datetime.fromtimestamp(log[5]).strftime(
                        '%Y-%m-%d %H:%M:%S')
                })

            return {
                'total': total_count,
                'logs': log_list,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        except Exception as e:
            print(f"获取管理员操作日志失败: {e}")
            return {}


def get_alert_records(start_date: Optional[str] = None,
                      end_date: Optional[str] = None,
                      status: Optional[str] = None) -> Dict[str, Any]:
    """获取异常监控与告警记录

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        status: 告警状态 unhandled/handled
    """
    with get_db_connection() as (conn, c):
        try:
            # 构建查询条件
            where_conditions = []
            params = []

            if start_date:
                start_timestamp = int(
                    datetime.fromisoformat(start_date).timestamp())
                where_conditions.append("created_at >= ?")
                params.append(start_timestamp)

            if end_date:
                end_timestamp = int(
                    datetime.fromisoformat(end_date).timestamp())
                where_conditions.append("created_at <= ?")
                params.append(end_timestamp)

            if status:
                where_conditions.append("status = ?")
                params.append(status)

            where_clause = (" AND ".join(where_conditions)
                            if where_conditions else "1=1")

            # 获取告警总数
            total_alerts = c.execute(f"""
                SELECT COUNT(*) FROM alert_records WHERE {where_clause}
            """, params).fetchone()[0]

            # 获取告警列表
            alerts = c.execute(f"""
                SELECT
                    id, alert_type, alert_level, description,
                    threshold_value, actual_value, status,
                    created_at, handled_by, handled_at, handle_note
                FROM alert_records
                WHERE {where_clause}
                ORDER BY created_at DESC
            """, params).fetchall()

            alert_list = []
            for alert in alerts:
                alert_list.append({
                    'id': alert[0],
                    'alert_type': alert[1],
                    'alert_level': alert[2],
                    'description': alert[3],
                    'threshold': f"{alert[4]}%" if alert[4] else None,
                    'actual': f"{alert[5]}%" if alert[5] else None,
                    'status': '已处理' if alert[6] == 'handled' else '未处理',
                    'created_at': datetime.fromtimestamp(alert[7]).strftime(
                        '%Y-%m-%d %H:%M:%S'),
                    'handled_by': alert[8],
                    'handled_at': (datetime.fromtimestamp(alert[9]).strftime(
                        '%Y-%m-%d %H:%M:%S') if alert[9] else None),
                    'handle_note': alert[10]
                })

            # 近7天告警趋势
            today_start = int(time.time()) - (int(time.time()) % 86400)
            alert_trend = []
            for i in range(7):
                day_start = today_start - i * 86400
                day_end = day_start + 86400

                count = c.execute("""
                    SELECT COUNT(*) FROM alert_records
                    WHERE created_at >= ? AND created_at < ?
                """, (day_start, day_end)).fetchone()[0]

                date_str = datetime.fromtimestamp(day_start).strftime(
                    '%Y-%m-%d')
                alert_trend.insert(0, {
                    'date': date_str,
                    'count': count
                })

            return {
                'total_alerts': total_alerts,
                'alerts': alert_list,
                'alert_trend': alert_trend,
                'timestamp': int(time.time())
            }
        except Exception as e:
            print(f"获取告警记录失败: {e}")
            return {}


def handle_alert(alert_id: int, admin_id: int, handle_note: str) -> bool:
    """处理告警记录

    Args:
        alert_id: 告警ID
        admin_id: 管理员ID
        handle_note: 处理备注
    """
    with get_db_connection() as (conn, c):
        try:
            handled_at = int(time.time())
            c.execute("""
                UPDATE alert_records
                SET status = 'handled', handled_by = ?,
                    handled_at = ?, handle_note = ?
                WHERE id = ?
            """, (admin_id, handled_at, handle_note, alert_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"处理告警失败: {e}")
            return False


# ============= 增强统计功能 (2025-10-20) =============


def get_user_segmentation(target_date: Optional[str] = None) -> Dict[str, Any]:
    """获取用户分群统计

    将用户分为：新用户、活跃用户、沉默用户、流失用户

    Args:
        target_date: 目标日期 YYYY-MM-DD，默认为今天

    Returns:
        {
            'new_users': 123,         # 新用户（7天内注册）
            'active_users': 456,      # 活跃用户（7天内有活动）
            'silent_users': 789,      # 沉默用户（30天未活跃）
            'lost_users': 234,        # 流失用户（60天未活跃）
            'total_users': 1602,      # 总用户数
            'segments': [
                {'segment': 'new', 'count': 123, 'percentage': 7.68},
                {'segment': 'active', 'count': 456, 'percentage': 28.46},
                {'segment': 'silent', 'count': 789, 'percentage': 49.25},
                {'segment': 'lost', 'count': 234, 'percentage': 14.61}
            ],
            'timestamp': 1729411200
        }
    """
    cache_key = f"user_segmentation_{target_date}"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            # 确定时间范围
            if not target_date:
                target_date = date.today().isoformat()

            current_time = int(
                datetime.fromisoformat(target_date).timestamp()
            )

            # 时间阈值
            seven_days_ago = current_time - 7 * 86400
            thirty_days_ago = current_time - 30 * 86400
            sixty_days_ago = current_time - 60 * 86400

            # 1. 新用户（7天内注册）
            new_users = c.execute("""
                SELECT COUNT(*) FROM users
                WHERE role != 'admin'
                AND created_at >= datetime(?, 'unixepoch')
            """, (seven_days_ago,)).fetchone()[0]

            # 2. 活跃用户（7天内有登录或行为记录）
            active_users = c.execute("""
                SELECT COUNT(DISTINCT user_id) FROM (
                    SELECT user_id FROM user_login_log
                    WHERE login_time >= ?
                    UNION
                    SELECT user_id FROM user_behavior_log
                    WHERE created_at >= ?
                )
            """, (seven_days_ago, seven_days_ago)).fetchone()[0]

            # 3. 总用户数（排除管理员）
            total_users = c.execute("""
                SELECT COUNT(*) FROM users WHERE role != 'admin'
            """).fetchone()[0]

            # 4. 流失用户（60天无活动）
            # 获取60天内有活动的用户
            active_60_days = c.execute("""
                SELECT COUNT(DISTINCT user_id) FROM (
                    SELECT user_id FROM user_login_log
                    WHERE login_time >= ?
                    UNION
                    SELECT user_id FROM user_behavior_log
                    WHERE created_at >= ?
                )
            """, (sixty_days_ago, sixty_days_ago)).fetchone()[0]

            lost_users = max(0, total_users - active_60_days)

            # 5. 沉默用户（30天无活动但未流失）
            active_30_days = c.execute("""
                SELECT COUNT(DISTINCT user_id) FROM (
                    SELECT user_id FROM user_login_log
                    WHERE login_time >= ?
                    UNION
                    SELECT user_id FROM user_behavior_log
                    WHERE created_at >= ?
                )
            """, (thirty_days_ago, thirty_days_ago)).fetchone()[0]

            # 沉默用户 = 60天内活跃 - 30天内活跃
            silent_users = max(0, active_60_days - active_30_days)

            # 计算百分比
            segments = []
            if total_users > 0:
                segments = [
                    {
                        'segment': 'new',
                        'label': '新用户',
                        'count': new_users,
                        'percentage': round(new_users / total_users * 100, 2)
                    },
                    {
                        'segment': 'active',
                        'label': '活跃用户',
                        'count': active_users,
                        'percentage': round(
                            active_users / total_users * 100, 2
                        )
                    },
                    {
                        'segment': 'silent',
                        'label': '沉默用户',
                        'count': silent_users,
                        'percentage': round(
                            silent_users / total_users * 100, 2
                        )
                    },
                    {
                        'segment': 'lost',
                        'label': '流失用户',
                        'count': lost_users,
                        'percentage': round(lost_users / total_users * 100, 2)
                    }
                ]

            result = {
                'new_users': new_users,
                'active_users': active_users,
                'silent_users': silent_users,
                'lost_users': lost_users,
                'total_users': total_users,
                'segments': segments,
                'timestamp': current_time
            }

            # 缓存5分钟
            set_statistics_cache(cache_key, result, 300)
            return result

        except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
            print(f"获取用户分群统计失败: {e}")
            return {}


def get_conversion_funnel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """获取用户行为转化漏斗

    漏斗阶段：注册 → 首次登录 → 首次计算 → 首次充值 → 套餐升级

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD

    Returns:
        {
            'funnel': [
                {'step': '注册', 'count': 1000, 'rate': 100.0},
                {'step': '首次登录', 'count': 800, 'rate': 80.0},
                {'step': '首次计算', 'count': 600, 'rate': 60.0},
                {'step': '首次充值', 'count': 200, 'rate': 20.0},
                {'step': '套餐升级', 'count': 50, 'rate': 5.0}
            ],
            'conversion_rates': {
                'register_to_login': 80.0,
                'login_to_calculate': 75.0,
                'calculate_to_pay': 33.3,
                'pay_to_upgrade': 25.0
            },
            'timestamp': 1729411200
        }
    """
    cache_key = f"conversion_funnel_{start_date}_{end_date}"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            # 如果未指定日期范围，默认最近30天
            if not end_date:
                end_date = date.today().isoformat()
            if not start_date:
                start_date = (date.today() - timedelta(days=30)).isoformat()

            # 转换为时间戳
            end_timestamp = int(
                datetime.fromisoformat(end_date).timestamp()
            )
            start_timestamp = int(
                datetime.fromisoformat(start_date).timestamp()
            )

            # 1. 注册用户数
            registered_users = c.execute("""
                SELECT COUNT(*) FROM users
                WHERE role != 'admin'
                AND created_at >= datetime(?, 'unixepoch')
                AND created_at <= datetime(?, 'unixepoch')
            """, (start_timestamp, end_timestamp)).fetchone()[0]

            # 2. 有登录记录的用户数
            logged_in_users = c.execute("""
                SELECT COUNT(DISTINCT u.id)
                FROM users u
                INNER JOIN user_login_log l ON u.id = l.user_id
                WHERE u.role != 'admin'
                AND u.created_at >= datetime(?, 'unixepoch')
                AND u.created_at <= datetime(?, 'unixepoch')
            """, (start_timestamp, end_timestamp)).fetchone()[0]

            # 3. 有计算行为的用户数
            calculated_users = c.execute("""
                SELECT COUNT(DISTINCT u.id)
                FROM users u
                INNER JOIN user_behavior_log b ON u.id = b.user_id
                WHERE u.role != 'admin'
                AND u.created_at >= datetime(?, 'unixepoch')
                AND u.created_at <= datetime(?, 'unixepoch')
                AND b.behavior_type = 'calculation'
            """, (start_timestamp, end_timestamp)).fetchone()[0]

            # 4. 有支付记录的用户数
            paid_users = c.execute("""
                SELECT COUNT(DISTINCT u.id)
                FROM users u
                INNER JOIN payment_orders p ON u.id = p.user_id
                WHERE u.role != 'admin'
                AND u.created_at >= datetime(?, 'unixepoch')
                AND u.created_at <= datetime(?, 'unixepoch')
                AND p.status = 'SUCCESS'
            """, (start_timestamp, end_timestamp)).fetchone()[0]

            # 5. 有升级记录的用户数
            upgraded_users = c.execute("""
                SELECT COUNT(DISTINCT u.id)
                FROM users u
                INNER JOIN payment_orders p ON u.id = p.user_id
                WHERE u.role != 'admin'
                AND u.created_at >= datetime(?, 'unixepoch')
                AND u.created_at <= datetime(?, 'unixepoch')
                AND p.status = 'SUCCESS'
                AND p.order_type = 'upgrade'
            """, (start_timestamp, end_timestamp)).fetchone()[0]

            # 构建漏斗数据
            funnel = []
            base_count = registered_users if registered_users > 0 else 1

            funnel.append({
                'step': '注册',
                'count': registered_users,
                'rate': 100.0
            })

            funnel.append({
                'step': '首次登录',
                'count': logged_in_users,
                'rate': round(logged_in_users / base_count * 100, 2)
            })

            funnel.append({
                'step': '首次计算',
                'count': calculated_users,
                'rate': round(calculated_users / base_count * 100, 2)
            })

            funnel.append({
                'step': '首次充值',
                'count': paid_users,
                'rate': round(paid_users / base_count * 100, 2)
            })

            funnel.append({
                'step': '套餐升级',
                'count': upgraded_users,
                'rate': round(upgraded_users / base_count * 100, 2)
            })

            # 计算阶段转化率
            conversion_rates = {}
            if registered_users > 0:
                conversion_rates['register_to_login'] = round(
                    logged_in_users / registered_users * 100, 2
                )
            if logged_in_users > 0:
                conversion_rates['login_to_calculate'] = round(
                    calculated_users / logged_in_users * 100, 2
                )
            if calculated_users > 0:
                conversion_rates['calculate_to_pay'] = round(
                    paid_users / calculated_users * 100, 2
                )
            if paid_users > 0:
                conversion_rates['pay_to_upgrade'] = round(
                    upgraded_users / paid_users * 100, 2
                )

            result = {
                'funnel': funnel,
                'conversion_rates': conversion_rates,
                'date_range': {
                    'start': start_date,
                    'end': end_date
                },
                'timestamp': int(time.time())
            }

            # 缓存5分钟
            set_statistics_cache(cache_key, result, 300)
            return result

        except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
            print(f"获取转化漏斗失败: {e}")
            return {}


def get_feature_usage_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """获取功能使用统计

    统计极速模式vs完整模式的使用情况

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD

    Returns:
        {
            'fast_mode_count': 5000,      # 极速模式使用次数
            'complete_mode_count': 3000,  # 完整模式使用次数
            'total_count': 8000,          # 总计算次数
            'mode_preference': 62.5,      # 极速模式偏好度(%)
            'daily_trend': [
                {
                    'date': '2025-10-01',
                    'fast': 150,
                    'complete': 80,
                    'total': 230
                },
                ...
            ],
            'timestamp': 1729411200
        }
    """
    cache_key = f"feature_usage_{start_date}_{end_date}"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            # 如果未指定日期范围，默认最近30天
            if not end_date:
                end_date = date.today().isoformat()
            if not start_date:
                start_date = (date.today() - timedelta(days=30)).isoformat()

            # 转换为时间戳
            end_timestamp = int(
                datetime.fromisoformat(end_date).timestamp()
            )
            start_timestamp = int(
                datetime.fromisoformat(start_date).timestamp()
            )

            # 1. 统计极速模式使用次数
            fast_mode_count = c.execute("""
                SELECT COUNT(*) FROM user_behavior_log
                WHERE behavior_type = 'calculation'
                AND calculation_mode = 'fast'
                AND created_at >= ?
                AND created_at <= ?
            """, (start_timestamp, end_timestamp)).fetchone()[0]

            # 2. 统计完整模式使用次数
            complete_mode_count = c.execute("""
                SELECT COUNT(*) FROM user_behavior_log
                WHERE behavior_type = 'calculation'
                AND calculation_mode = 'complete'
                AND created_at >= ?
                AND created_at <= ?
            """, (start_timestamp, end_timestamp)).fetchone()[0]

            # 3. 总计算次数
            total_count = fast_mode_count + complete_mode_count

            # 4. 计算极速模式偏好度
            mode_preference = 0
            if total_count > 0:
                mode_preference = round(
                    fast_mode_count / total_count * 100, 2
                )

            # 5. 每日使用趋势
            daily_trend = []
            current = start_timestamp
            while current <= end_timestamp:
                day_start = current
                day_end = current + 86400

                # 当日极速模式次数
                day_fast = c.execute("""
                    SELECT COUNT(*) FROM user_behavior_log
                    WHERE behavior_type = 'calculation'
                    AND calculation_mode = 'fast'
                    AND created_at >= ?
                    AND created_at < ?
                """, (day_start, day_end)).fetchone()[0]

                # 当日完整模式次数
                day_complete = c.execute("""
                    SELECT COUNT(*) FROM user_behavior_log
                    WHERE behavior_type = 'calculation'
                    AND calculation_mode = 'complete'
                    AND created_at >= ?
                    AND created_at < ?
                """, (day_start, day_end)).fetchone()[0]

                date_str = datetime.fromtimestamp(day_start).strftime(
                    '%Y-%m-%d'
                )
                daily_trend.append({
                    'date': date_str,
                    'fast': day_fast,
                    'complete': day_complete,
                    'total': day_fast + day_complete
                })

                current += 86400

            # 6. 用户偏好统计
            user_preference = c.execute("""
                SELECT
                    calculation_mode,
                    COUNT(DISTINCT user_id) as user_count
                FROM user_behavior_log
                WHERE behavior_type = 'calculation'
                AND calculation_mode IS NOT NULL
                AND created_at >= ?
                AND created_at <= ?
                GROUP BY calculation_mode
            """, (start_timestamp, end_timestamp)).fetchall()

            mode_users = {}
            for row in user_preference:
                mode_users[row[0]] = row[1]

            result = {
                'fast_mode_count': fast_mode_count,
                'complete_mode_count': complete_mode_count,
                'total_count': total_count,
                'mode_preference': mode_preference,
                'daily_trend': daily_trend,
                'mode_users': mode_users,
                'date_range': {
                    'start': start_date,
                    'end': end_date
                },
                'timestamp': int(time.time())
            }

            # 缓存5分钟
            set_statistics_cache(cache_key, result, 300)
            return result

        except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
            print(f"获取功能使用统计失败: {e}")
            return {}


def get_enhanced_revenue_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """获取增强版收入统计

    区分首充、续费、升级订单，并计算转化率

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD

    Returns:
        {
            'first_payment': {'count': 100, 'amount': 8900.00},
            'renewal': {'count': 50, 'amount': 4500.00},
            'upgrade': {'count': 30, 'amount': 6000.00},
            'total': {'count': 180, 'amount': 19400.00},
            'conversion_rate': {
                'free_to_paid': 12.5,      # 免费转付费率
                'efficiency_to_pro': 35.0   # 效率版升级率
            },
            'order_distribution': [
                {'type': '首充', 'count': 100, 'percentage': 55.5},
                {'type': '续费', 'count': 50, 'percentage': 27.8},
                {'type': '升级', 'count': 30, 'percentage': 16.7}
            ],
            'timestamp': 1729411200
        }
    """
    cache_key = f"enhanced_revenue_{start_date}_{end_date}"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            # 如果未指定日期范围，默认最近30天
            if not end_date:
                end_date = date.today().isoformat()
            if not start_date:
                start_date = (date.today() - timedelta(days=30)).isoformat()

            # 转换为时间戳
            end_timestamp = int(
                datetime.fromisoformat(end_date).timestamp()
            )
            start_timestamp = int(
                datetime.fromisoformat(start_date).timestamp()
            )

            # 1. 首充订单统计
            first_payment = c.execute("""
                SELECT
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) / 100.0 as amount
                FROM payment_orders
                WHERE status = 'SUCCESS'
                AND order_type = 'first_payment'
                AND created_at >= ?
                AND created_at <= ?
            """, (start_timestamp, end_timestamp)).fetchone()

            first_payment_data = {
                'count': first_payment[0],
                'amount': round(first_payment[1], 2)
            }

            # 2. 续费订单统计
            renewal = c.execute("""
                SELECT
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) / 100.0 as amount
                FROM payment_orders
                WHERE status = 'SUCCESS'
                AND order_type = 'renewal'
                AND created_at >= ?
                AND created_at <= ?
            """, (start_timestamp, end_timestamp)).fetchone()

            renewal_data = {
                'count': renewal[0],
                'amount': round(renewal[1], 2)
            }

            # 3. 升级订单统计
            upgrade = c.execute("""
                SELECT
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) / 100.0 as amount
                FROM payment_orders
                WHERE status = 'SUCCESS'
                AND order_type = 'upgrade'
                AND created_at >= ?
                AND created_at <= ?
            """, (start_timestamp, end_timestamp)).fetchone()

            upgrade_data = {
                'count': upgrade[0],
                'amount': round(upgrade[1], 2)
            }

            # 4. 未标记类型的订单
            unmarked = c.execute("""
                SELECT
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) / 100.0 as amount
                FROM payment_orders
                WHERE status = 'SUCCESS'
                AND (order_type IS NULL OR order_type = '')
                AND created_at >= ?
                AND created_at <= ?
            """, (start_timestamp, end_timestamp)).fetchone()

            unmarked_data = {
                'count': unmarked[0],
                'amount': round(unmarked[1], 2)
            }

            # 5. 总计
            total_count = (first_payment_data['count'] +
                           renewal_data['count'] +
                           upgrade_data['count'] +
                           unmarked_data['count'])
            total_amount = (first_payment_data['amount'] +
                            renewal_data['amount'] +
                            upgrade_data['amount'] +
                            unmarked_data['amount'])

            # 6. 计算转化率
            conversion_rate = {}

            # 免费用户转付费率
            free_users = c.execute("""
                SELECT COUNT(*) FROM users
                WHERE user_type = 'free'
                AND role != 'admin'
                AND created_at >= datetime(?, 'unixepoch')
                AND created_at <= datetime(?, 'unixepoch')
            """, (start_timestamp, end_timestamp)).fetchone()[0]

            if free_users > 0:
                paid_users = c.execute("""
                    SELECT COUNT(DISTINCT user_id)
                    FROM payment_orders
                    WHERE status = 'SUCCESS'
                    AND user_id IN (
                        SELECT id FROM users
                        WHERE user_type = 'free'
                        AND created_at >= datetime(?, 'unixepoch')
                        AND created_at <= datetime(?, 'unixepoch')
                    )
                """, (start_timestamp, end_timestamp)).fetchone()[0]

                conversion_rate['free_to_paid'] = round(
                    paid_users / free_users * 100, 2
                )

            # 效率版升级到专业版的转化率
            efficiency_users = c.execute("""
                SELECT COUNT(*) FROM users
                WHERE user_type = 'efficiency'
                AND role != 'admin'
            """).fetchone()[0]

            if efficiency_users > 0:
                upgraded_users = c.execute("""
                    SELECT COUNT(DISTINCT user_id)
                    FROM payment_orders
                    WHERE status = 'SUCCESS'
                    AND order_type = 'upgrade'
                    AND description LIKE '%专业版%'
                    AND created_at >= ?
                    AND created_at <= ?
                """, (start_timestamp, end_timestamp)).fetchone()[0]

                conversion_rate['efficiency_to_pro'] = round(
                    upgraded_users / efficiency_users * 100, 2
                )

            # 7. 订单类型分布
            order_distribution = []
            if total_count > 0:
                order_distribution = [
                    {
                        'type': '首充',
                        'count': first_payment_data['count'],
                        'percentage': round(
                            first_payment_data['count'] / total_count * 100, 2
                        )
                    },
                    {
                        'type': '续费',
                        'count': renewal_data['count'],
                        'percentage': round(
                            renewal_data['count'] / total_count * 100, 2
                        )
                    },
                    {
                        'type': '升级',
                        'count': upgrade_data['count'],
                        'percentage': round(
                            upgrade_data['count'] / total_count * 100, 2
                        )
                    }
                ]

                if unmarked_data['count'] > 0:
                    order_distribution.append({
                        'type': '未标记',
                        'count': unmarked_data['count'],
                        'percentage': round(
                            unmarked_data['count'] / total_count * 100, 2
                        )
                    })

            result = {
                'first_payment': first_payment_data,
                'renewal': renewal_data,
                'upgrade': upgrade_data,
                'unmarked': unmarked_data,
                'total': {
                    'count': total_count,
                    'amount': round(total_amount, 2)
                },
                'conversion_rate': conversion_rate,
                'order_distribution': order_distribution,
                'date_range': {
                    'start': start_date,
                    'end': end_date
                },
                'timestamp': int(time.time())
            }

            # 缓存5分钟
            set_statistics_cache(cache_key, result, 300)
            return result

        except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
            print(f"获取增强收入统计失败: {e}")
            return {}


def get_dau_mau_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取DAU/MAU统计

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)

    Returns:
        dict: {
            'dau': 日活跃用户数,
            'wau': 周活跃用户数,
            'mau': 月活跃用户数,
            'dau_trend': [{date, count}],  # 最近30天DAU趋势
        }
    """
    cache_key = f"dau_mau_{start_date}_{end_date}"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            current_time = int(time.time())
            today_start = current_time - (current_time % 86400)
            week_start = today_start - (7 * 86400)
            month_start = today_start - (30 * 86400)

            # DAU (今日活跃)
            dau = c.execute("""
                SELECT COUNT(DISTINCT user_id)
                FROM user_behavior_log
                WHERE created_at >= ?
            """, (today_start,)).fetchone()[0]

            # WAU (7日活跃)
            wau = c.execute("""
                SELECT COUNT(DISTINCT user_id)
                FROM user_behavior_log
                WHERE created_at >= ?
            """, (week_start,)).fetchone()[0]

            # MAU (30日活跃)
            mau = c.execute("""
                SELECT COUNT(DISTINCT user_id)
                FROM user_behavior_log
                WHERE created_at >= ?
            """, (month_start,)).fetchone()[0]

            # DAU趋势（最近30天）
            dau_trend = []
            for i in range(30):
                day_start = today_start - (i * 86400)
                day_end = day_start + 86400

                count = c.execute("""
                    SELECT COUNT(DISTINCT user_id)
                    FROM user_behavior_log
                    WHERE created_at >= ? AND created_at < ?
                """, (day_start, day_end)).fetchone()[0]

                dau_trend.append({
                    'date': datetime.fromtimestamp(day_start).strftime(
                        '%Y-%m-%d'
                    ),
                    'count': count
                })

            dau_trend.reverse()

            result = {
                'dau': dau,
                'wau': wau,
                'mau': mau,
                'dau_trend': dau_trend,
                'timestamp': current_time
            }

            # 缓存10分钟
            set_statistics_cache(cache_key, result, 600)
            return result

        except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
            print(f"获取DAU/MAU统计失败: {e}")
            return {}


def get_payment_records(
    page: int = 1,
    per_page: int = 20,
    plan_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取充值记录列表

    Args:
        page: 页码
        per_page: 每页数量
        plan_code: 套餐代码筛选
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        dict: {
            'records': [{订单信息}],
            'total': 总记录数,
            'page': 当前页,
            'per_page': 每页数量
        }
    """
    with get_db_connection() as (conn, c):
        try:
            # 构建查询条件
            where_clauses = ["po.status = 'SUCCESS'"]
            params = []

            if plan_code:
                where_clauses.append("po.description LIKE ?")
                params.append(f"%{plan_code}%")

            if start_date:
                start_ts = int(
                    datetime.strptime(start_date, '%Y-%m-%d').timestamp()
                )
                where_clauses.append("po.created_at >= ?")
                params.append(start_ts)

            if end_date:
                end_ts = int(
                    datetime.strptime(
                        end_date + ' 23:59:59', '%Y-%m-%d %H:%M:%S'
                    ).timestamp()
                )
                where_clauses.append("po.created_at <= ?")
                params.append(end_ts)

            where_sql = " AND ".join(where_clauses)

            # 获取总数
            total = c.execute(
                f"SELECT COUNT(*) FROM payment_orders po WHERE {where_sql}",
                params
            ).fetchone()[0]

            # 获取分页数据
            offset = (page - 1) * per_page
            query_params = params + [per_page, offset]

            c.execute(f"""
                SELECT
                    po.order_id,
                    po.user_id,
                    u.username,
                    po.amount,
                    po.description,
                    po.duration,
                    po.order_type,
                    po.created_at
                FROM payment_orders po
                LEFT JOIN users u ON po.user_id = u.id
                WHERE {where_sql}
                ORDER BY po.created_at DESC
                LIMIT ? OFFSET ?
            """, query_params)

            columns = [col[0] for col in c.description]
            rows = c.fetchall()

            records = []
            for row in rows:
                record = dict(zip(columns, row))
                # 格式化时间
                if record['created_at']:
                    record['created_at_str'] = datetime.fromtimestamp(
                        record['created_at']
                    ).strftime('%Y-%m-%d %H:%M:%S')
                # 格式化金额
                record['amount_yuan'] = record['amount'] / 100
                records.append(record)

            return {
                'records': records,
                'total': total,
                'page': page,
                'per_page': per_page
            }

        except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
            print(f"获取充值记录失败: {e}")
            return {
                'records': [], 'total': 0,
                'page': page, 'per_page': per_page
            }


def get_calculation_consumption_stats():
    """
    获取计算次数消耗统计

    Returns:
        dict: {
            'by_plan': [{plan_code, total_users, avg_used, avg_remaining}],
            'top_users': [{username, user_type, used, remaining}]
        }
    """
    cache_key = "calculation_consumption"
    cached = get_statistics_cache(cache_key)
    if cached:
        return cached

    with get_db_connection() as (conn, c):
        try:
            # 按套餐统计
            c.execute("""
                SELECT
                    subscription_type as plan_code,
                    COUNT(*) as total_users,
                    AVG(
                        CASE
                            WHEN subscription_type = 'efficiency' THEN
                                500 - remaining_calculations
                            WHEN subscription_type = 'professional' THEN
                                0
                            ELSE 10 - remaining_calculations
                        END
                    ) as avg_used,
                    AVG(remaining_calculations) as avg_remaining
                FROM users
                WHERE subscription_type IN (
                    'free', 'efficiency', 'professional'
                )
                GROUP BY subscription_type
            """)

            columns = [col[0] for col in c.description]
            rows = c.fetchall()
            by_plan = [dict(zip(columns, row)) for row in rows]

            # TOP使用用户
            c.execute("""
                SELECT
                    username,
                    subscription_type as user_type,
                    remaining_calculations
                FROM users
                WHERE subscription_type IN ('free', 'efficiency')
                ORDER BY remaining_calculations ASC
                LIMIT 20
            """)

            columns = [col[0] for col in c.description]
            rows = c.fetchall()
            top_users = []
            for row in rows:
                user = dict(zip(columns, row))
                # 计算已使用次数
                limit = 500 if user['user_type'] == 'efficiency' else 10
                user['used'] = limit - user['remaining_calculations']
                user['remaining'] = user['remaining_calculations']
                top_users.append(user)

            result = {
                'by_plan': by_plan,
                'top_users': top_users,
                'timestamp': int(time.time())
            }

            # 缓存10分钟
            set_statistics_cache(cache_key, result, 600)
            return result

        except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
            print(f"获取计算消耗统计失败: {e}")
            return {'by_plan': [], 'top_users': []}


def get_login_records(
    page: int = 1,
    per_page: int = 20,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    获取登录记录

    Args:
        page: 页码
        per_page: 每页数量
        user_id: 用户ID筛选

    Returns:
        dict: {
            'records': [{登录信息}],
            'total': 总记录数,
            'page': 当前页,
            'per_page': 每页数量
        }
    """
    with get_db_connection() as (conn, c):
        try:
            # 构建查询条件
            where_sql = "1=1"
            params = []

            if user_id:
                where_sql += " AND ull.user_id = ?"
                params.append(user_id)

            # 获取总数
            total = c.execute(
                f"SELECT COUNT(*) FROM user_login_log ull WHERE {where_sql}",
                params
            ).fetchone()[0]

            # 获取分页数据
            offset = (page - 1) * per_page
            query_params = params + [per_page, offset]

            c.execute(f"""
                SELECT
                    ull.id,
                    ull.user_id,
                    u.username,
                    u.subscription_type,
                    ull.login_time,
                    ull.ip_address,
                    ull.device_type
                FROM user_login_log ull
                LEFT JOIN users u ON ull.user_id = u.id
                WHERE {where_sql}
                ORDER BY ull.login_time DESC
                LIMIT ? OFFSET ?
            """, query_params)

            columns = [col[0] for col in c.description]
            rows = c.fetchall()

            records = []
            for row in rows:
                record = dict(zip(columns, row))
                # 格式化时间
                if record['login_time']:
                    record['login_time_str'] = datetime.fromtimestamp(
                        record['login_time']
                    ).strftime('%Y-%m-%d %H:%M:%S')
                records.append(record)

            return {
                'records': records,
                'total': total,
                'page': page,
                'per_page': per_page
            }

        except (sqlite3.Error, KeyError, TypeError, ValueError) as e:
            print(f"获取登录记录失败: {e}")
            return {
                'records': [], 'total': 0,
                'page': page, 'per_page': per_page
            }
