# -*- coding: utf-8 -*-
"""
套餐升级折抵系统
实现统一的升级计费逻辑
"""

import os
from typing import Dict, Any, Optional
import time


# 套餐层级映射（价格从数据库plans表读取）
PLAN_LEVEL_MAP = {
    'free': 0,
    'efficiency_promo': 1,
    'efficiency': 1,
    'professional': 2,
    'enterprise': 3
}


class SubscriptionUpgrade:
    """套餐升级折抵系统"""

    @staticmethod
    def calculate_remaining_value(
        billing_cycle: str,
        amount_paid: float,
        end_timestamp: int
    ) -> Dict[str, Any]:
        """
        计算当前套餐的剩余价值

        Args:
            billing_cycle: 计费周期（month/year）
            amount_paid: 实际支付金额
            end_timestamp: 订阅结束时间戳

        Returns:
            Dict 包含：
            - remaining_days: 剩余天数
            - daily_price: 日均价
            - remaining_value: 剩余价值
            - cycle_days: 周期天数
        """
        current_time = int(time.time())

        # 计算剩余天数
        remaining_seconds = end_timestamp - current_time
        remaining_days = max(0.0, remaining_seconds / (24 * 3600))

        # 计算周期天数
        cycle_days = 365 if billing_cycle == 'year' else 30

        # 计算日均价（使用实际支付金额）
        daily_price = amount_paid / cycle_days

        # 计算剩余价值
        remaining_value = daily_price * remaining_days

        return {
            'remaining_days': remaining_days,
            'daily_price': daily_price,
            'remaining_value': remaining_value,
            'cycle_days': cycle_days,
            'amount_paid': amount_paid
        }

    @staticmethod
    def calculate_upgrade_cost(
        current_plan: str,
        current_cycle: str,
        current_paid: float,
        current_end: int,
        target_plan: str,
        target_cycle: str
    ) -> Dict[str, Any]:
        """
        计算升级所需支付的差价

        Args:
            current_plan: 当前套餐
            current_cycle: 当前周期（month/year）
            current_paid: 当前已支付金额
            current_end: 当前订阅结束时间戳
            target_plan: 目标套餐
            target_cycle: 目标周期（month/year）

        Returns:
            Dict 包含：
            - target_price: 目标套餐价格
            - remaining_value: 剩余价值
            - difference: 应付差价
            - can_upgrade: 是否可以升级
            - message: 提示信息
        """
        # 从数据库获取套餐配置（避免硬编码价格）
        from db_utils import get_plan_by_code

        target_plan_config = get_plan_by_code(target_plan)
        if not target_plan_config:
            return {
                'can_upgrade': False,
                'message': f'目标套餐不存在: {target_plan}'
            }

        # 从数据库读取价格（根据TEST_MODE决定使用测试价还是实际价）
        test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        if test_mode:
            # 测试模式：使用测试价格
            if target_cycle == 'year':
                target_price = target_plan_config.get('test_price_year')
            else:
                target_price = target_plan_config.get('test_price_month')
        else:
            # 正式模式：使用实际价格
            if target_cycle == 'year':
                target_price = target_plan_config.get('actual_price_year')
            else:
                target_price = target_plan_config.get('actual_price_month')

        if target_price is None or target_price == 0:
            return {
                'can_upgrade': False,
                'message': (
                    f'{target_plan_config["plan_name"]}'
                    f'不支持{target_cycle}周期'
                )
            }

        # 计算当前套餐剩余价值
        # 免费版用户没有剩余价值
        if current_plan == 'free' or current_end is None:
            remaining_info = {
                'remaining_days': 0,
                'daily_price': 0,
                'remaining_value': 0,
                'cycle_days': 0,
                'amount_paid': 0
            }
        else:
            remaining_info = SubscriptionUpgrade.calculate_remaining_value(
                current_cycle, current_paid, current_end
            )

        # 计算差价
        difference = target_price - remaining_info['remaining_value']

        # 如果差价小于0，用户无需支付（直接升级）
        actual_payment = max(0, difference)

        return {
            'can_upgrade': True,
            'target_plan': target_plan,
            'target_plan_name': target_plan_config.get(
                'plan_name', target_plan
            ),
            'target_cycle': target_cycle,
            'target_price': target_price,
            'current_plan': current_plan,
            'current_cycle': current_cycle,
            'remaining_days': remaining_info['remaining_days'],
            'daily_price': remaining_info['daily_price'],
            'remaining_value': remaining_info['remaining_value'],
            'difference': difference,
            'actual_payment': actual_payment,
            'message': '升级方案已计算',
            'details': {
                'current_info': remaining_info,
                'calculation': {
                    'formula': '目标价格 - 剩余价值 = 应付差价',
                    'target_price': target_price,
                    'remaining_value': remaining_info['remaining_value'],
                    'difference': difference
                }
            }
        }

    @staticmethod
    def get_current_subscription_info(
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        获取用户当前订阅信息

        Returns:
            Dict 包含当前订阅的所有信息，或 None
        """
        from db_utils import get_db_connection

        try:
            from db_adapter import adapt_sql
            with get_db_connection() as (conn, cursor):
                sql = adapt_sql("""
                    SELECT subscription_type, subscription_expires,
                           last_paid_amount, billing_cycle
                    FROM users
                    WHERE id = ?
                """)
                cursor.execute(sql, (user_id,))

                result = cursor.fetchone()
                if not result:
                    return None

                (sub_type, sub_expires, last_paid,
                 billing_cycle) = result

                # 如果是免费版或没有订阅信息
                if not sub_type or sub_type == 'free':
                    return {
                        'subscription_type': 'free',
                        'subscription_expires': None,
                        'last_paid_amount': 0,
                        'billing_cycle': 'month',
                        'is_active': True
                    }

                return {
                    'subscription_type': sub_type,
                    'subscription_expires': sub_expires,
                    'last_paid_amount': last_paid or 0,
                    'billing_cycle': billing_cycle or 'month',
                    'is_active': sub_expires and sub_expires > time.time()
                }

        except Exception as e:
            print(f"获取订阅信息失败: {e}")
            return None

    @staticmethod
    def execute_upgrade(
        user_id: int,
        target_plan: str,
        target_cycle: str,
        payment_order_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行套餐升级

        Args:
            user_id: 用户ID
            target_plan: 目标套餐
            target_cycle: 目标周期
            payment_order_id: 支付订单ID（如果需要支付）

        Returns:
            升级结果
        """
        from db_utils import get_db_connection

        try:
            # 1. 获取当前订阅信息
            current_sub = SubscriptionUpgrade.get_current_subscription_info(
                user_id
            )
            if not current_sub:
                return {'success': False, 'message': '无法获取当前订阅信息'}

            # 2. 计算升级成本
            upgrade_info = SubscriptionUpgrade.calculate_upgrade_cost(
                current_plan=current_sub['subscription_type'],
                current_cycle=current_sub['billing_cycle'],
                current_paid=current_sub['last_paid_amount'],
                current_end=current_sub.get('subscription_expires', 0),
                target_plan=target_plan,
                target_cycle=target_cycle
            )

            if not upgrade_info['can_upgrade']:
                return {
                    'success': False,
                    'message': upgrade_info.get('message', '无法升级')
                }

            # 3. 更新用户订阅信息
            current_time = int(time.time())
            # duration可能是 "year", "1_year", "month", "1_month"
            is_year = target_cycle in ['year', '1_year']
            target_days = 365 if is_year else 30

            # 判断是否为续费（当前套餐和目标套餐相同）
            current_plan = current_sub['subscription_type']
            is_renewal = (current_plan == target_plan or
                          (current_plan == 'efficiency_promo' and
                           target_plan == 'efficiency'))

            if is_renewal:
                # 续费：从到期时间开始累加
                current_expires = current_sub.get('subscription_expires', 0)
                if current_expires and current_expires > current_time:
                    # 如果还未到期，从到期时间开始累加
                    new_end_time = current_expires + target_days * 24 * 3600
                    print(f"🔧 续费模式: 从到期时间累加, "
                          f"原到期时间={current_expires}, "
                          f"增加{target_days}天, 新到期时间={new_end_time}")
                else:
                    # 如果已到期，从当前时间开始计算
                    new_end_time = current_time + target_days * 24 * 3600
                    print(f"🔧 续费模式: 已过期，从当前时间开始, "
                          f"增加{target_days}天, 新到期时间={new_end_time}")
            else:
                # 升级：从当前时间开始计算
                new_end_time = current_time + target_days * 24 * 3600
                print(f"🔧 升级模式: 从当前时间开始, "
                      f"增加{target_days}天, 新到期时间={new_end_time}")

            print(f"🔧 计算新到期时间: target_cycle={target_cycle}, "
                  f"is_year={is_year}, days={target_days}, "
                  f"is_renewal={is_renewal}")

            # 处理 efficiency_promo：实际订阅类型是 efficiency
            # 检查是否是首月优惠订单（从订单描述中读取，更严谨）
            actual_subscription_type = target_plan
            efficiency_promo_used = 0

            # 从订单信息中读取首月优惠标记（最可靠的方式）
            # 优先从订单描述中判断，因为订单描述在创建时就已经包含了
            # "首月优惠"标记
            if payment_order_id:
                try:
                    from db_utils import _safe_adapt_sql
                    with get_db_connection() as (conn, cursor):
                        sql = _safe_adapt_sql(
                            "SELECT description FROM payment_orders "
                            "WHERE order_id = ?",
                            conn
                        )
                        cursor.execute(sql, (payment_order_id,))
                        order_result = cursor.fetchone()
                        if order_result and '首月优惠' in order_result[0]:
                            if (target_plan == 'efficiency' and
                                    target_cycle in ['month', '1_month']):
                                efficiency_promo_used = 1
                                print(
                                    "🎉 检测到首月优惠升级（从订单描述确认），"
                                    "标记 efficiency_promo_used=1"
                                )
                except Exception as e:
                    print(f"⚠️ 读取订单信息失败: {e}")

            # 兼容旧的efficiency_promo类型
            if target_plan == 'efficiency_promo':
                actual_subscription_type = 'efficiency'
                efficiency_promo_used = 1

            # 规范化 billing_cycle 为 "year" 或 "month"
            billing_cycle = 'year' if is_year else 'month'

            from db_adapter import adapt_sql
            from db_utils import _is_postgresql_connection as is_pg
            try:
                import psycopg2.errors as pg_errors
            except ImportError:
                pg_errors = None

            with get_db_connection() as (conn, cursor):
                # 尝试使用整数时间戳（适用于生产环境INTEGER类型）
                # 如果失败，回退到to_timestamp()（适用于测试环境timestamp类型）
                try:
                    sql = adapt_sql("""
                        UPDATE users
                        SET subscription_type = ?,
                            user_type = ?,
                            subscription_expires = ?,
                            billing_cycle = ?,
                            last_paid_amount = ?,
                            subscription_start = ?,
                            efficiency_promo_used = ?
                        WHERE id = ?
                    """)
                    cursor.execute(sql, (
                        actual_subscription_type, actual_subscription_type,
                        new_end_time, billing_cycle,
                        upgrade_info['target_price'],
                        current_time, efficiency_promo_used, user_id
                    ))
                except Exception as e:
                    # 如果失败且是PostgreSQL，尝试使用to_timestamp()
                    # 检查是否是类型不匹配错误
                    is_datatype_error = False
                    if pg_errors and isinstance(e, pg_errors.DatatypeMismatch):
                        is_datatype_error = True
                    else:
                        error_str = str(e)
                        if (is_pg(conn) and
                                ('subscription_start' in error_str or
                                 'DatatypeMismatch' in error_str or
                                 'timestamp' in error_str.lower() or
                                 'integer' in error_str.lower())):
                            is_datatype_error = True

                    if is_datatype_error and is_pg(conn):
                        # PostgreSQL中事务失败后需要回滚
                        try:
                            conn.rollback()
                        except (AttributeError, TypeError, RuntimeError,
                                ConnectionError):
                            pass  # 忽略回滚错误
                        # 重新执行UPDATE，使用to_timestamp()
                        sql = adapt_sql("""
                            UPDATE users
                            SET subscription_type = ?,
                                user_type = ?,
                                subscription_expires = ?,
                                billing_cycle = ?,
                                last_paid_amount = ?,
                                subscription_start = to_timestamp(?),
                                efficiency_promo_used = ?
                            WHERE id = ?
                        """)
                        cursor.execute(sql, (
                            actual_subscription_type, actual_subscription_type,
                            new_end_time, billing_cycle,
                            upgrade_info['target_price'],
                            current_time, efficiency_promo_used, user_id
                        ))
                    else:
                        raise

                # 4. 记录升级历史
                sql = adapt_sql("""
                    INSERT INTO subscription_upgrade_history
                    (user_id, from_plan, to_plan, from_cycle, to_cycle,
                     upgrade_time, remaining_value, difference_paid,
                     target_price, payment_order_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """)
                cursor.execute(sql, (
                    user_id,
                    current_sub['subscription_type'],
                    target_plan,
                    current_sub['billing_cycle'],
                    billing_cycle,  # 使用规范化的 billing_cycle
                    current_time,
                    upgrade_info['remaining_value'],
                    upgrade_info['actual_payment'],
                    upgrade_info['target_price'],
                    payment_order_id
                ))

                conn.commit()

            return {
                'success': True,
                'message': '升级成功',
                'upgrade_info': upgrade_info,
                'new_end_time': new_end_time
            }

        except Exception as e:
            print(f"执行升级失败: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'升级失败: {str(e)}'}

    @staticmethod
    def get_upgrade_options(user_id: int) -> Dict[str, Any]:
        """
        获取用户可用的升级选项

        Returns:
            所有可升级的套餐及对应的折抵信息
        """
        from db_utils import get_plans, get_plan_by_code

        current_sub = SubscriptionUpgrade.get_current_subscription_info(
            user_id
        )
        if not current_sub:
            return {'success': False, 'message': '无法获取订阅信息'}

        current_plan = current_sub['subscription_type']

        # 从数据库获取当前套餐信息
        current_plan_config = get_plan_by_code(current_plan)
        if current_plan_config:
            current_plan_name = current_plan_config['plan_name']
            current_level = PLAN_LEVEL_MAP.get(current_plan, 0)
        else:
            current_plan_name = '未知'
            current_level = 0

        # 检查用户是否使用过效率版首月优惠
        promo_used = False
        from db_utils import get_db_connection, _safe_adapt_sql
        import sqlite3
        try:
            import psycopg2.errors as pg_errors
        except ImportError:
            pg_errors = None

        try:
            with get_db_connection() as (conn, cursor):
                sql = _safe_adapt_sql(
                    "SELECT efficiency_promo_used FROM users WHERE id = ?",
                    conn
                )
                cursor.execute(sql, (user_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    promo_used = True
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            # SQLite数据库错误
            print(f"⚠️ 查询用户优惠状态失败（SQLite）: {e}")
            promo_used = False
        except Exception as e:
            # PostgreSQL或其他数据库错误
            if pg_errors and isinstance(
                e, (pg_errors.UndefinedColumn, pg_errors.UndefinedTable)
            ):
                print(f"⚠️ 查询用户优惠状态失败（PostgreSQL）: {e}")
                promo_used = False
            else:
                # 其他未知错误，记录并继续
                print(f"⚠️ 查询用户优惠状态失败: {e}")
                promo_used = False

        # 从数据库获取所有可用套餐
        all_plans = get_plans()
        upgrade_options = []

        for plan_config in all_plans:
            plan_code = plan_config['plan_code']

            # 确定套餐层级
            target_level = PLAN_LEVEL_MAP.get(plan_code, 0)

            # 只能升级到更高级的套餐
            if target_level <= current_level:
                continue

            # 检查套餐是否启用
            if not plan_config.get('is_active', 0):
                continue

            # 计算月付和年付的升级成本
            # 根据TEST_MODE决定使用测试价还是实际价
            test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
            for cycle in ['month', 'year']:
                # 检查是否可以使用效率版首月优惠
                # 条件：1. 当前套餐是免费版 2. 目标套餐是效率版 3. 选择月付 4. 用户未使用过优惠
                is_efficiency_promo = (
                    current_plan == 'free' and
                    plan_code == 'efficiency' and
                    cycle == 'month' and
                    not promo_used
                )

                if is_efficiency_promo:
                    # 使用首月优惠价：1元
                    target_price = 1.0
                    actual_payment = 1.0
                    remaining_value = 0.0
                    difference = 1.0
                    is_promo = True
                else:
                    # 正常价格计算
                    if test_mode:
                        # 测试模式：使用测试价格
                        if cycle == 'year':
                            target_price = plan_config.get('test_price_year')
                        else:
                            target_price = plan_config.get('test_price_month')
                    else:
                        # 正式模式：使用实际价格
                        if cycle == 'year':
                            target_price = plan_config.get(
                                'actual_price_year'
                            )
                        else:
                            target_price = plan_config.get(
                                'actual_price_month'
                            )

                    if target_price is None or target_price == 0:
                        continue

                    # 计算升级成本
                    upgrade_cost = SubscriptionUpgrade.calculate_upgrade_cost(
                        current_plan=current_sub['subscription_type'],
                        current_cycle=current_sub['billing_cycle'],
                        current_paid=current_sub['last_paid_amount'],
                        current_end=current_sub.get('subscription_expires', 0),
                        target_plan=plan_code,
                        target_cycle=cycle
                    )

                    if not upgrade_cost['can_upgrade']:
                        continue

                    actual_payment = upgrade_cost['actual_payment']
                    remaining_value = upgrade_cost['remaining_value']
                    difference = upgrade_cost['difference']
                    is_promo = False

                # 添加到升级选项
                upgrade_options.append({
                    'plan_key': plan_code,
                    'plan_name': plan_config['plan_name'],
                    'cycle': cycle,
                    'cycle_display': '月付' if cycle == 'month' else '年付',
                    'target_price': target_price,
                    'remaining_value': remaining_value,
                    'difference': difference,
                    'actual_payment': actual_payment,
                    'is_promo': is_promo,  # 标记是否为优惠订单
                    'features': plan_config.get('features', [])
                })

        return {
            'success': True,
            'current_plan': current_plan,
            'current_plan_name': current_plan_name,
            'upgrade_options': upgrade_options
        }
