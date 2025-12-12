# -*- coding: utf-8 -*-
"""
支付回调补偿服务
定期扫描pending状态的订单，主动查询微信支付状态进行补偿
防止回调丢失导致用户支付成功但服务未开通
"""

import time
import logging
from typing import List, Dict, Any
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PaymentCompensationService:
    """支付补偿服务"""

    def __init__(self):
        """初始化补偿服务"""
        self.check_interval = 300  # 5分钟检查一次
        self.pending_timeout = 600  # pending状态超过10分钟需要补偿
        self.max_check_age = 86400  # 只检查24小时内的订单

    def get_pending_orders(self) -> List[Dict[str, Any]]:
        """获取需要补偿的pending订单"""
        try:
            from db_adapter import get_db_connection

            current_time = int(time.time())
            check_start_time = current_time - self.max_check_age
            pending_threshold = current_time - self.pending_timeout

            with get_db_connection() as (_, cursor):
                from db_adapter import adapt_placeholders
                sql = """
                    SELECT order_id, user_id, amount, description,
                           created_at, duration
                    FROM payment_orders
                    WHERE status = 'PENDING'
                      AND created_at >= ?
                      AND created_at <= ?
                    ORDER BY created_at ASC
                """
                adapted_sql = adapt_placeholders(sql, 2)
                cursor.execute(
                    adapted_sql, (check_start_time, pending_threshold)
                )

                results = cursor.fetchall()

                orders = []
                for row in results:
                    orders.append({
                        'order_id': row[0],
                        'user_id': row[1],
                        'amount': row[2],
                        'description': row[3],
                        'created_at': row[4],
                        'duration': row[5]
                    })

                return orders

        except Exception as e:
            logger.error(f"获取pending订单失败: {e}")
            return []

    def get_paid_orders_not_processed(self) -> List[Dict[str, Any]]:
        """
        获取PAID状态但可能未处理的订单
        这些订单可能因为回调处理失败而需要补偿
        """
        try:
            from db_adapter import get_db_connection

            current_time = int(time.time())
            check_start_time = current_time - self.max_check_age
            # PAID订单超过5分钟未处理需要补偿
            paid_threshold = current_time - 300

            with get_db_connection() as (_, cursor):
                from db_adapter import adapt_placeholders
                sql = """
                    SELECT order_id, user_id, amount, description,
                           created_at, duration, updated_at
                    FROM payment_orders
                    WHERE status = 'PAID'
                      AND created_at >= ?
                      AND updated_at <= ?
                    ORDER BY updated_at ASC
                """
                adapted_sql = adapt_placeholders(sql, 2)
                cursor.execute(adapted_sql, (check_start_time, paid_threshold))

                results = cursor.fetchall()

                orders = []
                for row in results:
                    orders.append({
                        'order_id': row[0],
                        'user_id': row[1],
                        'amount': row[2],
                        'description': row[3],
                        'created_at': row[4],
                        'duration': row[5],
                        'updated_at': row[6] if len(row) > 6 else row[4]
                    })

                return orders

        except Exception as e:
            logger.error(f"获取PAID订单失败: {e}")
            return []

    @staticmethod
    def compensate_order(order_id: str) -> bool:
        """
        补偿单个订单

        Args:
            order_id: 订单ID

        Returns:
            bool: 是否补偿成功
        """
        try:
            from payment_handler import PaymentHandler

            logger.info(f"开始补偿订单: {order_id}")

            # 查询微信支付状态
            result = PaymentHandler.query_payment_status(order_id)

            if result.get("success"):
                status = result.get("status")
                logger.info(f"订单 {order_id} 微信状态: {status}")

                if status == "SUCCESS":
                    # 支付成功，触发业务逻辑
                    logger.info(
                        f"订单 {order_id} 已支付，开始处理业务逻辑"
                    )
                    PaymentHandler.handle_payment_success(order_id)
                    logger.info(f"✅ 订单 {order_id} 补偿成功")
                    return True

                elif status in ["CLOSED", "REVOKED", "PAYERROR"]:
                    # 支付失败，更新状态即可
                    logger.info(f"订单 {order_id} 支付失败，状态: {status}")
                    return False

                else:
                    # 仍在pending状态，暂不处理
                    logger.info(f"订单 {order_id} 仍在处理中")
                    return False
            else:
                logger.warning(
                    f"查询订单 {order_id} 状态失败: "
                    f"{result.get('message')}"
                )
                return False

        except Exception as e:
            logger.error(f"补偿订单 {order_id} 失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def run_compensation_check(self):
        """执行一次补偿检查"""
        logger.info("开始执行支付补偿检查...")

        # 1. 检查PENDING状态的订单
        pending_orders = self.get_pending_orders()

        # 2. 检查PAID状态但可能未处理的订单
        paid_orders = self.get_paid_orders_not_processed()

        total_orders = len(pending_orders) + len(paid_orders)
        if total_orders == 0:
            logger.info("没有需要补偿的订单")
            return

        logger.info(
            f"发现 {len(pending_orders)} 个PENDING订单, "
            f"{len(paid_orders)} 个PAID订单需要补偿"
        )

        success_count = 0

        # 处理PENDING订单
        for order in pending_orders:
            order_id = order['order_id']
            created_time = datetime.fromtimestamp(order['created_at'])
            age_minutes = (time.time() - order['created_at']) / 60

            logger.info(
                f"处理PENDING订单: {order_id}, "
                f"创建时间: {created_time}, "
                f"已等待: {age_minutes:.1f}分钟"
            )

            if self.compensate_order(order_id):
                success_count += 1

            # 避免请求过快
            time.sleep(1)

        # 处理PAID订单（可能回调处理失败）
        for order in paid_orders:
            order_id = order['order_id']
            updated_time = datetime.fromtimestamp(order['updated_at'])
            age_minutes = (time.time() - order['updated_at']) / 60

            logger.info(
                f"处理PAID订单（可能未处理）: {order_id}, "
                f"更新时间: {updated_time}, "
                f"已等待: {age_minutes:.1f}分钟"
            )

            # 对于PAID订单，直接调用handle_payment_success
            try:
                from payment_handler import PaymentHandler
                PaymentHandler.handle_payment_success(order_id)
                logger.info(f"✅ PAID订单 {order_id} 补偿成功")
                success_count += 1
            except Exception as e:
                logger.error(f"❌ PAID订单 {order_id} 补偿失败: {e}")

            # 避免请求过快
            time.sleep(1)

        logger.info(
            f"补偿检查完成: 共 {total_orders} 个订单, "
            f"成功补偿 {success_count} 个"
        )

    def start_daemon(self):
        """启动守护进程，定期执行补偿检查"""
        logger.info(
            f"支付补偿服务已启动，检查间隔: {self.check_interval}秒"
        )

        while True:
            try:
                self.run_compensation_check()
            except Exception as e:
                logger.error(f"补偿检查异常: {e}")
                import traceback
                logger.error(traceback.format_exc())

            # 等待下次检查
            logger.info(
                f"等待 {self.check_interval} 秒后进行下次检查..."
            )
            time.sleep(self.check_interval)


def main():
    """主函数"""
    service = PaymentCompensationService()
    service.start_daemon()


if __name__ == "__main__":
    main()
