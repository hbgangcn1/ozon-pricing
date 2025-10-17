"""
统计与运营看板数据服务
提供各类统计数据查询和分析功能
"""

import time
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any

try:
    from .db_utils import (
        get_db_connection, get_statistics_cache, set_statistics_cache
    )
except ImportError:
    from db_utils import (
        get_db_connection, get_statistics_cache, set_statistics_cache
    )


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
