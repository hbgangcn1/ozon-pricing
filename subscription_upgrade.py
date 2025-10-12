# -*- coding: utf-8 -*-
"""
套餐升级折抵系统
实现统一的升级计费逻辑
"""

from typing import Dict, Any, Optional
import time


# 套餐配置
SUBSCRIPTION_PLANS = {
    'free': {
        'name': '免费版',
        'price_month': 0,
        'price_year': 0,
        'features': ['每日10次计算', '1个物流模板'],
        'level': 0
    },
    'efficiency_promo': {
        'name': '效率版首月优惠',
        'price_month': 1.0,  # 首月1元
        'price_year': None,  # 首月优惠没有年付
        'features': ['无限计算', '3个物流模板'],
        'level': 1,
        'is_promo': True,
        'next_plan': 'efficiency'  # 首月后自动转为正常效率版价格
    },
    'efficiency': {
        'name': '效率版',
        'price_month': 14.9,
        'price_year': 149.0,
        'features': ['无限计算', '3个物流模板'],
        'level': 1
    },
    'professional': {
        'name': '专业版',
        'price_month': 149.0,
        'price_year': 1499.0,
        'features': ['无限计算', '无限物流模板', '多物流比价'],
        'level': 2
    },
    'enterprise': {
        'name': '企业版',
        'price_month': 999.0,
        'price_year': 9999.0,
        'features': ['所有功能', '专属客服', '定制开发'],
        'level': 3
    }
}


class SubscriptionUpgrade:
    """套餐升级折抵系统"""

    @staticmethod
    def calculate_remaining_value(
        current_plan: str,
        billing_cycle: str,
        amount_paid: float,
        end_timestamp: int
    ) -> Dict[str, Any]:
        """
        计算当前套餐的剩余价值

        Args:
            current_plan: 当前套餐类型（如 efficiency, professional）
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
        # 检查套餐是否存在
        if target_plan not in SUBSCRIPTION_PLANS:
            return {
                'can_upgrade': False,
                'message': f'目标套餐不存在: {target_plan}'
            }

        # 获取目标套餐价格
        target_plan_config = SUBSCRIPTION_PLANS[target_plan]
        if target_cycle == 'year':
            target_price = target_plan_config.get('price_year')
        else:
            target_price = target_plan_config.get('price_month')

        if target_price is None:
            return {
                'can_upgrade': False,
                'message': f'{target_plan_config["name"]}不支持{target_cycle}周期'
            }

        # 计算当前套餐剩余价值
        remaining_info = SubscriptionUpgrade.calculate_remaining_value(
            current_plan, current_cycle, current_paid, current_end
        )

        # 计算差价
        difference = target_price - remaining_info['remaining_value']

        # 如果差价小于0，用户无需支付（直接升级）
        actual_payment = max(0, difference)

        return {
            'can_upgrade': True,
            'target_plan': target_plan,
            'target_plan_name': target_plan_config['name'],
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
    def get_current_subscription_info(user_id: int) -> Optional[Dict[str, Any]]:
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
            target_days = 365 if target_cycle == 'year' else 30
            new_end_time = current_time + target_days * 24 * 3600

            with get_db_connection() as (conn, cursor):
                # 更新订阅信息
                cursor.execute("""
                    UPDATE users
                    SET subscription_type = ?,
                        user_type = ?,
                        subscription_expires = ?,
                        billing_cycle = ?,
                        last_paid_amount = ?
                    WHERE id = ?
                """, (
                    target_plan, target_plan, new_end_time,
                    target_cycle, upgrade_info['target_price'],
                    user_id
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
                    target_cycle,
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
        current_sub = SubscriptionUpgrade.get_current_subscription_info(
            user_id
        )
        if not current_sub:
            return {'success': False, 'message': '无法获取订阅信息'}

        current_plan = current_sub['subscription_type']
        current_level = SUBSCRIPTION_PLANS.get(current_plan, {}).get('level', 0)

        # 计算所有可升级的套餐
        upgrade_options = []

        for plan_key, plan_config in SUBSCRIPTION_PLANS.items():
            target_level = plan_config.get('level', 0)

            # 只能升级到更高级的套餐
            if target_level <= current_level:
                continue

            # 计算月付和年付的升级成本
            for cycle in ['month', 'year']:
                price_key = f'price_{cycle}'
                target_price = plan_config.get(price_key)

                if target_price is None or target_price == 0:
                    continue

                # 计算升级成本
                upgrade_cost = SubscriptionUpgrade.calculate_upgrade_cost(
                    current_plan=current_sub['subscription_type'],
                    current_cycle=current_sub['billing_cycle'],
                    current_paid=current_sub['last_paid_amount'],
                    current_end=current_sub.get('subscription_expires', 0),
                    target_plan=plan_key,
                    target_cycle=cycle
                )

                if upgrade_cost['can_upgrade']:
                    upgrade_options.append({
                        'plan_key': plan_key,
                        'plan_name': plan_config['name'],
                        'cycle': cycle,
                        'cycle_display': '月付' if cycle == 'month' else '年付',
                        'target_price': target_price,
                        'remaining_value': upgrade_cost['remaining_value'],
                        'difference': upgrade_cost['difference'],
                        'actual_payment': upgrade_cost['actual_payment'],
                        'features': plan_config['features']
                    })

        return {
            'success': True,
            'current_plan': current_plan,
            'current_plan_name': SUBSCRIPTION_PLANS.get(
                current_plan, {}
            ).get('name', '未知'),
            'upgrade_options': upgrade_options
        }

