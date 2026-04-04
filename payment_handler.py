# -*- coding: utf-8 -*-
"""
支付处理模块
为物流支付系统提供核心支付处理功能
"""

import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

try:
    from db_adapter import get_db_connection, adapt_sql

    _db_available = True
except ImportError:
    _db_available = False
    get_db_connection = None

    def adapt_sql(sql):
        return sql


try:
    from wechat_pay_v3_api import wechat_pay_v3

    _wechat_available = True
except ImportError:
    _wechat_available = False
    wechat_pay_v3 = None


def _extract_plan_code(description: str) -> str:
    """从订单描述中提取套餐代码"""
    if "效率版" in description:
        return "efficiency"
    elif "专业版" in description:
        return "professional"
    elif "企业版" in description:
        return "enterprise"
    return "efficiency"


def _parse_duration(duration: str) -> int:
    """解析订阅时长字符串为天数"""
    if "年" in duration:
        return 365
    elif "月" in duration:
        return 30
    return 30


class PaymentHandler:
    """支付处理器，提供微信支付查询和订单处理静态方法"""

    @staticmethod
    def query_payment_status(order_id: str) -> Dict[str, Any]:
        """
        查询微信支付状态

        Args:
            order_id: 订单ID

        Returns:
            Dict with keys: success, status, message
        """
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
                "message": str(e),
            }

    @staticmethod
    def handle_payment_success(order_id: str) -> None:
        """
        处理支付成功，更新订单状态和用户订阅

        Args:
            order_id: 订单ID

        Raises:
            ValueError: 订单不存在时
        """
        if not _db_available or get_db_connection is None:
            raise RuntimeError("数据库不可用")

        try:
            with get_db_connection() as (conn, cursor):
                sql = adapt_sql(
                    "SELECT user_id, description, duration, status"
                    " FROM payment_orders WHERE order_id = ?"
                )
                cursor.execute(sql, (order_id,))
                row = cursor.fetchone()

                if row is None:
                    raise ValueError(f"订单不存在: {order_id}")

                user_id, description, duration, status = row

                if status == "SUCCESS":
                    logger.info(f"订单已处于SUCCESS状态，跳过: {order_id}")
                    return

                current_time = int(time.time())

                update_sql = adapt_sql(
                    "UPDATE payment_orders SET status='SUCCESS',"
                    " updated_at=? WHERE order_id=?"
                )
                cursor.execute(update_sql, (current_time, order_id))

                plan_code = _extract_plan_code(description or "")
                duration_days = _parse_duration(duration or "月")
                expiry = current_time + duration_days * 86400

                user_sql = adapt_sql(
                    "UPDATE users SET subscription_type=?,"
                    " subscription_expires=?, remaining_calculations=-1,"
                    " updated_at=? WHERE id=?"
                )
                cursor.execute(user_sql, (plan_code, expiry, current_time, user_id))
                conn.commit()
                logger.info(f"支付成功处理完成: 订单{order_id}, 用户{user_id}")
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"处理支付成功时出错: {e}")
            raise

    @staticmethod
    def update_order_status(order_id: str, status: str) -> None:
        """
        更新订单状态

        Args:
            order_id: 订单ID
            status: 新状态
        """
        if not _db_available or get_db_connection is None:
            raise RuntimeError("数据库不可用")

        try:
            with get_db_connection() as (conn, cursor):
                current_time = int(time.time())
                sql = adapt_sql(
                    "UPDATE payment_orders SET status=?, updated_at=? WHERE order_id=?"
                )
                cursor.execute(sql, (status, current_time, order_id))
                conn.commit()
                logger.info(f"订单状态已更新: {order_id} -> {status}")
        except Exception as e:
            logger.error(f"更新订单状态时出错: {e}")
            raise


class _PaymentHandlerModule:
    """模块级支付处理器，处理微信支付回调通知"""

    def process_wechat_notify(self, notify_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理微信支付回调通知

        Args:
            notify_data: 通知数据

        Returns:
            Dict with keys: success, message, out_trade_no (and others)
        """
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
                    PaymentHandler.update_order_status(out_trade_no, "PAID")

            return result
        except Exception as e:
            logger.error(f"处理微信通知时出错: {e}")
            return {
                "success": False,
                "message": str(e),
                "out_trade_no": "",
            }


payment_handler = _PaymentHandlerModule()
