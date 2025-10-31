# -*- coding: utf-8 -*-
"""
支付处理模块
集成微信支付到现有的用户界面中
高优先级安全改进：订单金额验证、用户ID验证、幂等性检查
"""

import streamlit as st
import time
import uuid
import logging
from typing import Dict, Any, Optional
from wechat_pay_v3_api import wechat_pay_v3
from wechat_pay_config import wechat_config
from db_utils import get_db_connection
from rate_limiter import get_limiter

# 配置日志
logger = logging.getLogger(__name__)

# 高优先级安全改进：支付金额阈值配置
PAYMENT_AMOUNT_THRESHOLD = 10000  # 10000分 = 100元，超过此金额需要人工审核


def determine_order_type(user_id: int, target_plan: str,
                         is_upgrade: bool = False) -> str:
    """
    判断订单类型

    Args:
        user_id: 用户ID
        target_plan: 目标套餐类型
        is_upgrade: 是否标记为升级

    Returns:
        'first_payment': 首充
        'renewal': 续费
        'upgrade': 升级
    """
    with get_db_connection() as (conn, c):
        # 1. 如果明确标记为升级，直接返回
        if is_upgrade:
            return 'upgrade'

        # 2. 查询用户历史成功订单数
        history_count = c.execute("""
            SELECT COUNT(*) FROM payment_orders
            WHERE user_id = ? AND status = 'SUCCESS'
        """, (user_id,)).fetchone()[0]

        # 3. 查询当前用户类型
        user_info = c.execute("""
            SELECT user_type FROM users WHERE id = ?
        """, (user_id,)).fetchone()

        if not user_info:
            return 'first_payment'

        current_user_type = user_info[0]

        # 4. 判断逻辑
        if history_count == 0:
            # 无历史订单，首充
            return 'first_payment'

        if current_user_type == 'free':
            # 从免费版升级，视为首充
            return 'first_payment'

        # 定义套餐层级
        hierarchy = {
            'free': 0,
            'efficiency': 1,
            'efficiency_promo': 1,
            'professional': 2,
            'enterprise': 3,
            'gratitude': 2
        }

        current_level = hierarchy.get(current_user_type, 0)
        # 从description中提取套餐类型
        target_level = hierarchy.get(target_plan, 0)

        if target_level > current_level:
            # 更高层级，升级
            return 'upgrade'
        else:
            # 同级或更低，续费
            return 'renewal'


class PaymentHandler:
    """支付处理类"""

    def __init__(self):
        """初始化支付处理器"""
        self.config = wechat_config

    @staticmethod
    def create_payment_order(user_id: int,
                             amount: int,
                             description: str,
                             duration: str = "month",
                             payment_type: str = "native",
                             is_upgrade: bool = False,
                             upgrade_info: Optional[Dict[str, Any]] = None
                             ) -> Dict[str, Any]:
        """
        创建支付订单（带限流保护）

        Args:
            user_id: 用户ID
            amount: 支付金额（分）
            description: 订单描述
            duration: 订阅时长（month/year）
            payment_type: 支付类型（native/jsapi）
            is_upgrade: 是否为套餐升级
            upgrade_info: 升级信息（包含折抵详情）

        Returns:
            Dict[str, Any]: 订单创建结果
        """
        # 限流检查：每分钟最多10次支付请求
        payment_limiter = get_limiter("payment_create", rate=10, per=60)
        limiter_key = f"payment_{user_id}"

        if not payment_limiter.is_allowed(limiter_key):
            retry_after = int(payment_limiter.get_retry_after(limiter_key)) + 1
            return {
                'success': False,
                'message': f'订单创建过于频繁，请 {retry_after} 秒后重试（每分钟最多 10 次）'
            }

        # 生成订单号
        order_id = f"PAY_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        # 保存订单到数据库
        try:
            with get_db_connection() as (conn, cursor):
                # 先检查用户是否存在
                cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
                if not cursor.fetchone():
                    return {"success": False, "message": f"用户ID {user_id} 不存在"}

                # 判断订单类型
                target_plan_type = 'unknown'
                # 尝试从description中提取套餐类型
                desc_lower = description.lower()
                if '效率版' in description or 'efficiency' in desc_lower:
                    target_plan_type = 'efficiency'
                elif '专业版' in description or 'professional' in desc_lower:
                    target_plan_type = 'professional'
                elif '企业版' in description or 'enterprise' in desc_lower:
                    target_plan_type = 'enterprise'
                elif '首月优惠' in description:
                    target_plan_type = 'efficiency_promo'

                order_type = determine_order_type(
                    user_id,
                    target_plan_type,
                    is_upgrade
                )

                # 保存订单信息（包含升级信息）
                if is_upgrade and upgrade_info:
                    cursor.execute("""
                        INSERT INTO payment_orders
                        (order_id, user_id, amount, description, duration,
                         status, created_at, is_upgrade, upgrade_from_plan,
                         upgrade_to_plan, remaining_value, order_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        order_id, user_id, amount, description, duration,
                        'PENDING', int(time.time()), 1,
                        upgrade_info.get('current_plan'),
                        upgrade_info.get('target_plan'),
                        upgrade_info.get('remaining_value', 0),
                        order_type
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO payment_orders
                        (order_id, user_id, amount, description, duration,
                         status, created_at, order_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (order_id, user_id, amount, description, duration,
                          'PENDING', int(time.time()), order_type))

                conn.commit()

        except Exception as e:
            return {"success": False, "message": f"订单创建失败: {str(e)}"}

        # 根据支付类型创建微信支付订单
        if payment_type == "native":
            result = wechat_pay_v3.create_native_order(
                order_id=order_id,
                total_amount=amount,
                description=description
            )
        elif payment_type == "jsapi":
            # 需要用户openid，这里暂时返回错误
            return {"success": False, "message": "JSAPI支付需要用户openid"}
        else:
            return {"success": False, "message": "不支持的支付类型"}

        if result["success"]:
            # 更新订单状态
            PaymentHandler.update_order_status(order_id, "CREATED")

            return {
                "success": True,
                "order_id": order_id,
                "code_url": result.get("code_url"),
                "prepay_id": result.get("prepay_id")
            }
        else:
            return result

    @staticmethod
    def query_payment_status(order_id: str) -> Dict[str, Any]:
        """
        查询支付状态

        Args:
            order_id: 订单号

        Returns:
            Dict[str, Any]: 查询结果
        """
        # 查询微信支付状态
        result = wechat_pay_v3.query_order(order_id)

        if result["success"]:
            trade_state = result.get("trade_state")

            # 更新本地订单状态
            if trade_state == "SUCCESS":
                PaymentHandler.update_order_status(order_id, "PAID")
            elif trade_state in ["CLOSED", "REVOKED", "PAYERROR"]:
                PaymentHandler.update_order_status(order_id, "FAILED")

            return {
                "success": True,
                "status": trade_state,
                "description": result.get("trade_state_desc", ""),
                "data": result.get("data", {})
            }
        else:
            return result

    @staticmethod
    def update_order_status(order_id: str, status: str):
        """更新订单状态（公开方法）"""
        try:
            with get_db_connection() as (conn, cursor):
                cursor.execute("""
                    UPDATE payment_orders
                    SET status = ?, updated_at = ?
                    WHERE order_id = ?
                """, (status, int(time.time()), order_id))

                conn.commit()

        except Exception as e:
            print(f"更新订单状态失败: {e}")

    @staticmethod
    def get_user_payment_history(user_id: int) -> list:
        """获取用户支付历史"""
        try:
            with get_db_connection() as (conn, cursor):
                cursor.execute("""
                    SELECT order_id, amount, description, status, created_at
                    FROM payment_orders
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 20
                """, (user_id,))

                results = cursor.fetchall()

            return [
                {
                    "order_id": row[0],
                    "amount": row[1],
                    "description": row[2],
                    "status": row[3],
                    "created_at": row[4]
                }
                for row in results
            ]

        except Exception as e:
            print(f"查询支付历史失败: {e}")
            return []

    @staticmethod
    def process_wechat_notify(notify_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理微信支付回调通知

        Args:
            notify_data: 通知数据

        Returns:
            Dict[str, Any]: 处理结果
        """
        print("🚀 PaymentHandler.process_wechat_notify 开始处理")
        result = wechat_pay_v3.process_notify(notify_data)
        print(f"🔧 wechat_pay_v3.process_notify 返回结果: {result}")

        if result["success"]:
            order_id = result.get("out_trade_no")
            transaction_id = result.get("transaction_id")
            decrypted_data = result.get("data", {})

            print(f"🔧 获取到订单ID: {order_id}")
            if order_id:
                # 高优先级安全改进：验证订单金额和用户ID
                validation_result = (
                    PaymentHandler._validate_payment_callback(
                        order_id, decrypted_data
                    )
                )

                if not validation_result["valid"]:
                    print(f"❌ 支付回调验证失败: {validation_result['message']}")
                    return {
                        "success": False,
                        "message": validation_result["message"]
                    }

                # 高优先级安全改进：幂等性检查
                if transaction_id:
                    idempotency_result = (
                        PaymentHandler._check_idempotency(
                            order_id, str(transaction_id)
                        )
                    )

                    if not idempotency_result["can_process"]:
                        print(
                            f"⚠️ 订单已处理（幂等性检查）: {order_id}, "
                            f"原因: {idempotency_result['reason']}"
                        )
                        return {
                            "success": True,
                            "message": "订单已处理",
                            "idempotent": True
                        }

                # 更新订单状态为已支付
                print(f"🔧 开始更新订单状态: {order_id}")
                PaymentHandler.update_order_status(order_id, "PAID")

                # 记录处理状态（防止重复处理）
                if transaction_id:
                    PaymentHandler._mark_order_processed(
                        order_id, str(transaction_id)
                    )

                # 这里可以添加业务逻辑，比如开通会员、增加计算次数等
                print(f"🔧 开始处理支付成功业务逻辑: {order_id}")
                PaymentHandler.handle_payment_success(order_id)
            else:
                print("❌ 未获取到订单ID")
        else:
            print(f"❌ 支付通知处理失败: {result.get('message', '未知错误')}")

        return result

    @staticmethod
    def _validate_payment_callback(
            order_id: str, decrypted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证支付回调数据（高优先级安全改进）

        Args:
            order_id: 订单ID
            decrypted_data: 解密后的回调数据

        Returns:
            Dict包含valid(bool)和message(str)
        """
        try:
            with get_db_connection() as (conn, cursor):
                # 查询订单信息
                cursor.execute("""
                    SELECT user_id, amount, status FROM payment_orders
                    WHERE order_id = ?
                """, (order_id,))

                order_info = cursor.fetchone()
                if not order_info:
                    return {
                        "valid": False,
                        "message": f"订单不存在: {order_id}"
                    }

                db_user_id, db_amount, db_status = order_info

                # 验证订单金额
                callback_amount = (
                    decrypted_data.get("amount", {}).get("total", 0)
                )
                if callback_amount != db_amount:
                    logger.error(
                        f"订单金额不匹配: 订单{order_id}, "
                        f"数据库金额={db_amount}, 回调金额={callback_amount}"
                    )
                    return {
                        "valid": False,
                        "message": "订单金额验证失败"
                    }

                # 验证用户ID（如果回调中包含用户信息）
                callback_user_id = decrypted_data.get("attach")
                if callback_user_id:
                    try:
                        callback_user_id_int = int(callback_user_id)
                        if callback_user_id_int != db_user_id:
                            logger.error(
                                f"用户ID不匹配: 订单{order_id}, "
                                f"数据库用户ID={db_user_id}, "
                                f"回调用户ID={callback_user_id_int}"
                            )
                            return {
                                "valid": False,
                                "message": "用户ID验证失败"
                            }
                    except (ValueError, TypeError):
                        # attach字段可能不是用户ID，忽略
                        pass

                # 检查订单状态（防止重复处理）
                if db_status == "SUCCESS":
                    return {
                        "valid": False,
                        "message": "订单已处理"
                    }

                return {"valid": True, "message": "验证通过"}

        except Exception as e:
            logger.error(f"验证支付回调数据失败: {e}")
            return {
                "valid": False,
                "message": f"验证失败: {str(e)}"
            }

    @staticmethod
    def _check_idempotency(
            order_id: str, transaction_id: str
    ) -> Dict[str, Any]:
        """
        检查幂等性（高优先级安全改进）

        Args:
            order_id: 订单ID
            transaction_id: 微信交易号

        Returns:
            Dict包含can_process(bool)和reason(str)
        """
        try:
            with get_db_connection() as (conn, cursor):
                # 检查订单是否已处理
                cursor.execute("""
                    SELECT status, wechat_transaction_id FROM payment_orders
                    WHERE order_id = ?
                """, (order_id,))

                order_info = cursor.fetchone()
                if not order_info:
                    return {
                        "can_process": True,
                        "reason": "订单不存在"
                    }

                status, existing_transaction_id = order_info

                # 如果订单已成功处理
                if status == "SUCCESS":
                    # 检查交易号是否一致
                    if existing_transaction_id == transaction_id:
                        return {
                            "can_process": False,
                            "reason": "订单已成功处理，交易号一致"
                        }
                    else:
                        logger.warning(
                            f"订单{order_id}交易号不一致: "
                            f"已有={existing_transaction_id}, "
                            f"当前={transaction_id}"
                        )
                        return {
                            "can_process": False,
                            "reason": "订单已处理但交易号不一致"
                        }

                return {"can_process": True, "reason": "订单未处理"}

        except Exception as e:
            logger.error(f"幂等性检查失败: {e}")
            # 失败时允许继续，但记录日志
            return {"can_process": True, "reason": "检查失败"}

    @staticmethod
    def _mark_order_processed(order_id: str, transaction_id: str):
        """
        标记订单已处理（高优先级安全改进）

        Args:
            order_id: 订单ID
            transaction_id: 微信交易号
        """
        try:
            with get_db_connection() as (conn, cursor):
                cursor.execute("""
                    UPDATE payment_orders
                    SET wechat_transaction_id = ?, updated_at = ?
                    WHERE order_id = ?
                """, (transaction_id, int(time.time()), order_id))
                conn.commit()
        except Exception as e:
            logger.error(f"标记订单已处理失败: {e}")

    @staticmethod
    def _check_payment_amount_threshold(amount: int) -> Dict[str, Any]:
        """
        检查支付金额阈值（高优先级安全改进）

        Args:
            amount: 支付金额（分）

        Returns:
            Dict包含needs_review(bool)和message(str)
        """
        if amount > PAYMENT_AMOUNT_THRESHOLD:
            logger.warning(
                f"大额支付告警: 金额={amount}分 "
                f"(>{PAYMENT_AMOUNT_THRESHOLD}分)"
            )
            return {
                "needs_review": True,
                "message": (
                    f"支付金额{amount/100:.2f}元超过阈值"
                    f"{PAYMENT_AMOUNT_THRESHOLD/100:.2f}元，需要人工审核"
                )
            }
        return {
            "needs_review": False,
            "message": "金额正常"
        }

    @staticmethod
    def handle_payment_success(order_id: str):
        """
        处理支付成功后的业务逻辑（带事务回滚机制）

        这是一个公开方法，可被补偿服务等外部模块调用

        Args:
            order_id: 订单ID
        """
        print(f"🔧 开始处理支付成功逻辑: 订单ID={order_id}")
        try:
            with get_db_connection() as (conn, cursor):
                # 获取订单信息（包含升级信息）
                cursor.execute("""
                    SELECT user_id, amount, description, duration, is_upgrade,
                           upgrade_from_plan, upgrade_to_plan, remaining_value
                    FROM payment_orders
                    WHERE order_id = ?
                """, (order_id,))

                order_info = cursor.fetchone()
                if not order_info:
                    print(f"❌ 未找到订单记录: {order_id}")
                    return

                print(f"✅ 找到订单记录: {order_info}")

                (user_id, amount, description, duration, is_upgrade,
                 upgrade_from, upgrade_to, remaining_value) = order_info

                # 高优先级安全改进：检查支付金额阈值
                threshold_check = (
                    PaymentHandler._check_payment_amount_threshold(amount)
                )
                if threshold_check["needs_review"]:
                    logger.warning(
                        f"订单{order_id}需要人工审核: "
                        f"{threshold_check['message']}"
                    )
                    # 标记订单为需要审核状态
                    cursor.execute("""
                        UPDATE payment_orders
                        SET status = 'REVIEW_NEEDED', updated_at = ?
                        WHERE order_id = ?
                    """, (int(time.time()), order_id))
                    conn.commit()
                    print(f"⚠️ 订单已标记为需要审核: {order_id}")
                    return

                # 判断是否为升级订单
                if is_upgrade:
                    print(f"🔄 这是一个升级订单: {upgrade_from} → {upgrade_to}")
                    print(f"   剩余价值折抵: ¥{remaining_value / 100:.2f}")
                    # 升级订单使用专门的处理逻辑
                    PaymentHandler._handle_upgrade_payment_success(
                        order_id, user_id, upgrade_to, duration,
                        amount / 100, remaining_value / 100
                    )
                    return

                # 根据duration字段判断订阅时长
                if duration == "year" or duration == "1_year":
                    days = 365  # 年付
                    duration_text = "年付"
                elif duration == "month" or duration == "1_month":
                    days = 30  # 月付
                    duration_text = "月付"
                else:
                    # 如果duration为None或其他值，默认为月付
                    days = 30
                    duration_text = "月付(默认)"
                    print(f"⚠️ duration字段异常: {duration}, 使用默认月付30天")

                print(f"🔧 订阅时长判断: duration={duration}, "
                      f"{duration_text}, {days}天, 描述={description}")

                # 获取用户当前订阅信息
                cursor.execute("""
                    SELECT subscription_type, subscription_expires, user_type
                    FROM users
                    WHERE id = ?
                """, (user_id,))
                user_info = cursor.fetchone()
                if user_info:
                    (current_sub_type, current_expires,
                     current_user_type) = user_info
                    print(
                        f"🔍 用户当前状态: "
                        f"subscription_type={current_sub_type}, "
                        f"subscription_expires={current_expires}, "
                        f"user_type={current_user_type}"
                    )
                else:
                    current_expires = None
                    print(f"⚠️ 未找到用户记录: user_id={user_id}")

                # 计算新的到期时间：在原有基础上累加
                current_time = int(time.time())
                from datetime import datetime

                if current_expires and current_expires > current_time:
                    # 如果还未到期，在原有到期时间基础上增加
                    old_expires_dt = datetime.fromtimestamp(current_expires)
                    new_expires = current_expires + days * 24 * 3600
                    new_expires_dt = datetime.fromtimestamp(new_expires)
                    print("🔧 续费模式：")
                    old_time_str = old_expires_dt.strftime('%Y-%m-%d %H:%M:%S')
                    print(
                        f"   原到期时间: {old_time_str} "
                        f"(时间戳={current_expires})"
                    )
                    print(f"   增加时长: {days}天")
                    new_time_str = new_expires_dt.strftime('%Y-%m-%d %H:%M:%S')
                    print(
                        f"   新到期时间: {new_time_str} "
                        f"(时间戳={new_expires})"
                    )
                else:
                    # 如果已过期或没有到期时间，从现在开始计算
                    new_expires = current_time + days * 24 * 3600
                    new_expires_dt = datetime.fromtimestamp(new_expires)
                    print("🔧 新订阅模式：")
                    current_dt = datetime.fromtimestamp(current_time)
                    current_time_str = current_dt.strftime('%Y-%m-%d %H:%M:%S')
                    print(f"   当前时间: {current_time_str}")
                    print(f"   增加时长: {days}天")
                    new_time_str = new_expires_dt.strftime('%Y-%m-%d %H:%M:%S')
                    print(
                        f"   新到期时间: {new_time_str} "
                        f"(时间戳={new_expires})"
                    )

                # 根据支付金额和描述处理业务逻辑
                subscription_type = None
                if ("专业版" in description or
                        "PROFESSIONAL" in description.upper()):
                    subscription_type = "professional"
                    print(f"🔧 处理专业版支付成功: 用户ID={user_id}, "
                          f"{duration_text}, {days}天")

                elif ("效率版" in description or
                      "EFFICIENCY" in description.upper()):
                    subscription_type = "efficiency"
                    print(f"🔧 处理效率版支付成功: 用户ID={user_id}, "
                          f"{duration_text}, {days}天, 描述={description}")

                if subscription_type:
                    # 确定计费周期
                    billing_cycle = (
                        'year' if duration in ['year', '1_year'] else 'month'
                    )
                    # 计算实际支付金额（转为元）
                    paid_amount = amount / 100

                    # 检查是否是首月优惠（金额为1元）
                    efficiency_promo_used = 0
                    if (subscription_type == "efficiency" and
                            paid_amount <= 1.5 and billing_cycle == 'month'):
                        efficiency_promo_used = 1
                        print("🎉 检测到首月优惠支付，标记 "
                              "efficiency_promo_used=1")

                    # 更新订阅信息（包含计费周期和支付金额）
                    cursor.execute("""
                        UPDATE users
                        SET subscription_type = ?,
                            subscription_expires = ?,
                            user_type = ?,
                            billing_cycle = ?,
                            last_paid_amount = ?,
                            subscription_start = ?,
                            efficiency_promo_used = ?
                        WHERE id = ?
                    """, (
                        subscription_type, new_expires,
                        subscription_type, billing_cycle,
                        paid_amount, current_time,
                        efficiency_promo_used, user_id
                    ))

                    # 验证更新结果
                    cursor.execute("""
                        SELECT subscription_type, subscription_expires,
                               user_type
                        FROM users
                        WHERE id = ?
                    """, (user_id,))
                    verify_info = cursor.fetchone()
                    if verify_info:
                        (verify_sub_type, verify_expires,
                         verify_user_type) = verify_info
                        verify_dt = datetime.fromtimestamp(verify_expires)
                        print(
                            f"✅ {subscription_type}订阅状态已更新并验证:"
                        )
                        print(f"   用户ID: {user_id}")
                        print(f"   订阅类型: {verify_sub_type}")
                        print(f"   用户类型: {verify_user_type}")
                        verify_time_str = verify_dt.strftime(
                            '%Y-%m-%d %H:%M:%S'
                        )
                        print(f"   到期时间: {verify_time_str}")
                        print(f"   时间戳: {verify_expires}")

                        # 计算剩余天数
                        days_remaining = (
                            (verify_expires - current_time) / (24 * 3600)
                        )
                        print(f"   剩余天数: {days_remaining:.1f}天")
                    else:
                        print("⚠️ 更新后无法验证用户信息")

                elif "计算次数" in description:
                    # 增加计算次数
                    cursor.execute("""
                        UPDATE users
                        SET calculations_remaining = calculations_remaining + ?
                        WHERE id = ?
                    """, (amount // 100, user_id))  # 假设1元=1次计算
                    print(f"✅ 计算次数已增加: {amount // 100}次")

                conn.commit()
                print(f"✅ 支付成功处理完成: 订单ID={order_id}")

        except Exception as e:
            print(f"❌ 处理支付成功逻辑失败: {e}")
            import traceback
            print(f"❌ 错误详情: {traceback.format_exc()}")
            # 数据库连接已自动回滚（由get_db_connection的上下文管理器处理）

    @staticmethod
    def _handle_upgrade_payment_success(
        order_id: str,
        user_id: int,
        target_plan: str,
        target_cycle: str,
        paid_amount: float,
        remaining_value: float
    ):
        """处理升级支付成功的业务逻辑"""
        print(f"🔄 处理套餐升级支付: 订单ID={order_id}")
        print(f"   用户ID={user_id}, 目标套餐={target_plan}")
        print(f"   支付金额=¥{paid_amount:.2f}, 折抵价值=¥{remaining_value:.2f}")

        try:
            from subscription_upgrade import SubscriptionUpgrade

            # 执行升级
            result = SubscriptionUpgrade.execute_upgrade(
                user_id=user_id,
                target_plan=target_plan,
                target_cycle=target_cycle,
                payment_order_id=order_id
            )

            if result['success']:
                print(f"✅ 套餐升级成功: {target_plan}")
                print(f"   新到期时间: {result.get('new_end_time')}")
            else:
                print(f"❌ 套餐升级失败: {result.get('message')}")

        except Exception as e:
            print(f"❌ 处理升级支付失败: {e}")
            import traceback
            traceback.print_exc()


def show_payment_page():
    """显示支付页面"""
    st.title("💳 支付中心")

    # 检查用户登录状态
    if 'user_id' not in st.session_state:
        st.error("请先登录")
        return

    user_id = st.session_state.user_id
    local_payment_handler = PaymentHandler()

    # 支付套餐选择
    st.subheader("📦 选择套餐")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        ### 🆓 免费版
        - 每月10次计算
        - 基础功能
        """)
        if st.button("当前套餐", key="free", disabled=True):
            pass

    with col2:
        st.markdown("""
        ### ⭐ 专业版
        - 无限次计算
        - 所有功能
        - ¥99/年
        """)
        if st.button("购买专业版", key="professional"):
            create_professional_payment(local_payment_handler, user_id)

    with col3:
        st.markdown("""
        ### 💰 购买计算次数
        - 每次计算 ¥1
        - 按需购买
        """)

        calc_amount = st.number_input("购买次数", min_value=1,
                                      max_value=1000, value=10)
        if st.button("购买计算次数", key="calculations"):
            create_calculation_payment(local_payment_handler, user_id,
                                       calc_amount)

    # 支付历史
    st.subheader("📋 支付历史")
    history = PaymentHandler.get_user_payment_history(user_id)

    if history:
        for record in history:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                with col1:
                    st.write(f"**{record['description']}**")
                    st.caption(f"订单号: {record['order_id']}")
                with col2:
                    st.write(f"¥{record['amount'] / 100:.2f}")
                with col3:
                    status_color = {"PAID": "✅", "PENDING": "⏳",
                                    "FAILED": "❌"}
                    st.write(f"{status_color.get(record['status'], '❓')} "
                             f"{record['status']}")
                with col4:
                    time_str = time.strftime('%Y-%m-%d %H:%M',
                                             time.localtime(
                                                 record['created_at']))
                    st.write(f"<small>{time_str}</small>",
                             unsafe_allow_html=True)
                st.divider()
    else:
        st.info("暂无支付记录")


def create_professional_payment(handler: PaymentHandler, user_id: int):
    """创建专业版支付订单"""
    result = PaymentHandler.create_payment_order(
        user_id=user_id,
        amount=9900,  # ¥99.00
        description="专业版会员 - 1年",
        payment_type="native"
    )

    if result["success"]:
        st.success("订单创建成功！")

        # 显示二维码
        if result.get("code_url"):
            st.subheader("📱 请使用微信扫描二维码完成支付")

            # 这里可以集成二维码生成库
            st.code(result["code_url"])
            st.info("请在微信中打开链接完成支付")

            # 轮询支付状态
            if st.button("检查支付状态"):
                check_payment_status(handler, result["order_id"])
        else:
            st.error("二维码生成失败")
    else:
        st.error(f"订单创建失败: {result['message']}")


def create_calculation_payment(handler: PaymentHandler, user_id: int,
                               amount: int):
    """创建计算次数支付订单"""
    result = PaymentHandler.create_payment_order(
        user_id=user_id,
        amount=amount * 100,  # 转换为分
        description=f"购买计算次数 - {amount}次",
        payment_type="native"
    )

    if result["success"]:
        st.success("订单创建成功！")

        if result.get("code_url"):
            st.subheader("📱 请使用微信扫描二维码完成支付")
            st.code(result["code_url"])
            st.info("请在微信中打开链接完成支付")

            if st.button("检查支付状态", key="check_calc"):
                check_payment_status(handler, result["order_id"])
        else:
            st.error("二维码生成失败")
    else:
        st.error(f"订单创建失败: {result['message']}")


def check_payment_status(handler: PaymentHandler, order_id: str):
    """检查支付状态"""
    _ = handler  # 消除未使用参数警告
    result = PaymentHandler.query_payment_status(order_id)

    if result["success"]:
        status = result["status"]
        if status == "SUCCESS":
            st.success("✅ 支付成功！您的账户已更新")
            st.rerun()
        elif status in ["CLOSED", "REVOKED", "PAYERROR"]:
            st.error("❌ 支付失败")
        else:
            st.warning("⏳ 支付处理中，请稍后再试")
    else:
        st.error(f"查询失败: {result['message']}")


# 全局支付处理器实例
payment_handler = PaymentHandler()
