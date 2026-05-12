# -*- coding: utf-8 -*-
"""
支付处理模块
为物流支付系统提供核心支付处理功能
"""
import time
import logging
from typing import Dict, Any

from database import AsyncSessionLocal
from services.payment_service import PaymentService

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
        logger.warning(
            "payment_handler.PaymentHandler is deprecated; "
            "use services.payment_service.PaymentService instead"
        )
        async with AsyncSessionLocal() as session:
            service = PaymentService(session)
            await service.handle_payment_success(order_id)

    @staticmethod
    async def update_order_status(order_id: str, status: str) -> None:
        logger.warning(
            "payment_handler.PaymentHandler is deprecated; "
            "use services.payment_service.PaymentService instead"
        )
        async with AsyncSessionLocal() as session:
            service = PaymentService(session)
            await service.update_order_status(order_id, status)
            await session.commit()
            logger.info(f"订单状态已更新: {order_id} -> {status}")
