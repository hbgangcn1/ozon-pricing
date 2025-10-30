# -*- coding: utf-8 -*-
"""
套餐升级折抵系统
实现统一的升级计费逻辑
"""

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

        # 从数据库读取价格
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
            with get_db_connection() as (conn, cursor):
                cursor.execute("""
                    SELECT subscription_type, subscription_expires,
                           last_paid_amount, billing_cycle
                    FROM users
                    WHERE id = ?
                """, (user_id,))

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
            new_end_time = current_time + target_days * 24 * 3600

            print(f"🔧 计算新到期时间: target_cycle={target_cycle}, "
                  f"is_year={is_year}, days={target_days}")

            # 处理 efficiency_promo：实际订阅类型是 efficiency
            actual_subscription_type = target_plan
            efficiency_promo_used = 0
            if target_plan == 'efficiency_promo':
                actual_subscription_type = 'efficiency'
                efficiency_promo_used = 1

            # 规范化 billing_cycle 为 "year" 或 "month"
            billing_cycle = 'year' if is_year else 'month'

            with get_db_connection() as (conn, cursor):
                # 更新订阅信息
                cursor.execute("""
                    UPDATE users
                    SET subscription_type = ?,
                        user_type = ?,
                        subscription_expires = ?,
                        billing_cycle = ?,
                        last_paid_amount = ?,
                        subscription_start = ?,
                        efficiency_promo_used = ?
                    WHERE id = ?
                """, (
                    actual_subscription_type, actual_subscription_type,
                    new_end_time, billing_cycle, upgrade_info['target_price'],
                    current_time, efficiency_promo_used, user_id
                ))

                # 4. 记录升级历史
                cursor.execute("""
                    INSERT INTO subscription_upgrade_history
                    (user_id, from_plan, to_plan, from_cycle, to_cycle,
                     upgrade_time, remaining_value, difference_paid,
                     target_price, payment_order_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
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
            for cycle in ['month', 'year']:
                if cycle == 'year':
                    target_price = plan_config.get('actual_price_year')
                else:
                    target_price = plan_config.get('actual_price_month')

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

                if upgrade_cost['can_upgrade']:
                    upgrade_options.append({
                        'plan_key': plan_code,
                        'plan_name': plan_config['plan_name'],
                        'cycle': cycle,
                        'cycle_display': '月付' if cycle == 'month' else '年付',
                        'target_price': target_price,
                        'remaining_value': upgrade_cost['remaining_value'],
                        'difference': upgrade_cost['difference'],
                        'actual_payment': upgrade_cost['actual_payment'],
                        'features': plan_config.get('features', '[]')
                    })

        return {
            'success': True,
            'current_plan': current_plan,
            'current_plan_name': current_plan_name,
            'upgrade_options': upgrade_options
        }
