# -*- coding: utf-8 -*-
"""
支付处理模块
为物流支付系统提供核心支付处理功能
"""

import time
import logging
from typing import Dict, Any

from database import AsyncSessionLocal
from sqlalchemy import select
from models.order import PaymentOrder
from models.user import User
from db.subscriptions import apply_subscription_change

logger = logging.getLogger(__name__)

try:
    from wechat_pay_v3_api import wechat_pay_v3

    _wechat_available = True
except ImportError:
    _wechat_available = False
    wechat_pay_v3 = None


def _extract_plan_code(description: str) -> str:
    if "效率版" in description:
        return "efficiency"
    elif "专业版" in description:
        return "professional"
    elif "企业版" in description:
        return "enterprise"
    return "efficiency"


def _parse_duration(duration: str) -> int:
    text = (duration or "").lower()
    if "年" in text or "year" in text:
        return 365
    if "月" in text or "month" in text:
        return 30
    return 30


class PaymentHandler:
    """支付处理器，提供微信支付查询和订单处理静态方法"""

    @staticmethod
    def query_payment_status(order_id: str) -> Dict[str, Any]:
        if not _wechat_available or wechat_pay_v3 is None:
            return {
                "success": False,
                "status": "UNKNOWN",
                "message": "微信支付模块不可用",
            }

        try:
            result = wechat_pay_v3.query_order(order_id)
            if result.get("success"):
                trade_state = result.get("trade_state", "")
                trade_state_desc = result.get("trade_state_desc", "")
                return {
                    "success": True,
                    "status": trade_state,
                    "message": trade_state_desc or trade_state,
                }
            else:
                return {
                    "success": False,
                    "status": "UNKNOWN",
                    "message": result.get("message", "查询失败"),
                }
        except Exception as e:
            logger.error(f"查询支付状态时出错: {e}")
            return {
                "success": False,
                "status": "UNKNOWN",
                "message": "查询支付状态失败",
            }

    @staticmethod
    async def handle_payment_success(order_id: str) -> None:
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(PaymentOrder).where(PaymentOrder.order_id == order_id).with_for_update()
                result = await session.execute(stmt)
                order = result.scalar_one_or_none()
                if order is None:
                    raise ValueError(f"订单不存在: {order_id}")
                if order.status == "SUCCESS":
                    logger.info(f"订单已处于SUCCESS状态，跳过: {order_id}")
                    return
                current_time = int(time.time())
                order.status = "SUCCESS"
                order.updated_at = current_time
                plan_code = _extract_plan_code(order.description or "")
                duration_days = _parse_duration(order.duration or "月")
                expiry = current_time + duration_days * 86400
                user = await session.get(User, order.user_id)
                if user:
                    await apply_subscription_change(
                        session,
                        order.user_id,
                        plan_code,
                        subscription_expires=expiry,
                        source="wechat_pay_legacy",
                    )
                    user.remaining_calculations = -1
                await session.commit()
                logger.info(f"支付成功处理完成: 订单{order_id}, 用户{order.user_id}")
            except ValueError:
                raise
            except Exception as e:
                await session.rollback()
                logger.error(f"处理支付成功时出错: {e}")
                raise

    @staticmethod
    async def update_order_status(order_id: str, status: str) -> None:
        async with AsyncSessionLocal() as session:
            try:
                order = (
                    await session.execute(
                        select(PaymentOrder).where(PaymentOrder.order_id == order_id)
                    )
                ).scalar_one_or_none()
                if order:
                    order.status = status
                    order.updated_at = int(time.time())
                await session.commit()
                logger.info(f"订单状态已更新: {order_id} -> {status}")
            except Exception as e:
                await session.rollback()
                logger.error(f"更新订单状态时出错: {e}")
                raise


class _PaymentHandlerModule:
    """模块级支付处理器，处理微信支付回调通知"""

    async def process_wechat_notify(
        self, notify_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not _wechat_available or wechat_pay_v3 is None:
            return {
                "success": False,
                "message": "微信支付模块不可用",
                "out_trade_no": "",
            }

        try:
            result = wechat_pay_v3.process_notify(notify_data)

            if "out_trade_no" not in result:
                result["out_trade_no"] = ""

            if result.get("success"):
                out_trade_no = result.get("out_trade_no", "")
                if out_trade_no:
                    await PaymentHandler.update_order_status(out_trade_no, "PAID")

            return result
        except Exception as e:
            logger.error(f"处理微信通知时出错: {e}")
            return {
                "success": False,
                "message": "处理通知失败",
                "out_trade_no": "",
            }


payment_handler = _PaymentHandlerModule()
