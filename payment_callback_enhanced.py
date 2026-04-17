# -*- coding: utf-8 -*-
"""
增强支付回调处理系统
解决高优先级问题：支付回调处理可靠性
"""

import asyncio
import time
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

# 配置日志
try:
    from logger_config import logger
except ImportError:
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)


@dataclass
class PaymentRetryRecord:
    """支付重试记录"""

    order_id: str
    retry_count: int
    first_attempt_time: float
    last_attempt_time: float
    next_retry_time: float
    error_message: Optional[str] = None
    max_retries: int = 5


@dataclass
class PaymentAlert:
    """支付告警记录"""

    timestamp: float
    alert_type: str  # 'queue_full', 'high_failure_rate', 'retry_exhausted'
    level: str  # 'warning', 'critical'
    message: str
    stats: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[float] = None


class PaymentCallbackEnhanced:
    """增强支付回调处理器"""

    MAX_RETRY_QUEUE_SIZE = 10000

    def __init__(
        self,
        queue_maxsize: int = 1000,
        queue_warning_threshold: int = 800,  # 80%阈值告警
        queue_critical_threshold: int = 900,  # 90%阈值严重告警
        max_retries: int = 3,  # 最多重试3次
        retry_interval: int = 60,  # 基础重试间隔（秒）
        check_interval: int = 60,  # 检查间隔（秒）
    ):
        self.queue_maxsize = queue_maxsize
        self.queue_warning_threshold = queue_warning_threshold
        self.queue_critical_threshold = queue_critical_threshold
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        self.check_interval = check_interval

        # 重试队列（延迟重试）
        self.retry_queue: List[PaymentRetryRecord] = []
        self.retry_lock = threading.Lock()

        # 统计信息
        self.stats = {
            "processed": 0,
            "failed": 0,
            "retried": 0,
            "queue_full_count": 0,
            "last_check_time": 0.0,
        }
        self.stats_lock = threading.Lock()

        # 告警记录
        self.alerts: List[PaymentAlert] = []
        self.alert_lock = threading.Lock()

        # 监控状态
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

    def enqueue_order(self, order_id: str) -> Dict[str, Any]:
        """直接处理订单，失败时进入重试队列"""
        logger.info(f"订单开始处理: {order_id}")
        success = self.process_order(order_id)
        if success:
            return {"success": True, "message": "订单已加入队列"}

        retry_count = self._get_retry_count(order_id)
        if retry_count > 0:
            return {
                "success": True,
                "message": "订单处理失败，已加入重试队列",
                "retry_count": retry_count,
            }

        return {"success": False, "message": "订单处理失败"}

    @staticmethod
    def _run_payment_success_handler(order_id: str):
        """在当前后台线程中同步执行异步支付成功处理。"""
        from payment_handler import PaymentHandler

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(PaymentHandler.handle_payment_success(order_id))
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    def _reject_retry_queue_entry(
        self, order_id: str, error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """拒绝新增重试记录并触发严重告警。"""
        message = (
            f"严重告警：重试队列已达到上限 "
            f"({len(self.retry_queue)}/{self.MAX_RETRY_QUEUE_SIZE})，拒绝订单 {order_id}"
        )
        with self.stats_lock:
            self.stats["queue_full_count"] += 1

        logger.critical(message)
        self.record_alert(
            "queue_full",
            "critical",
            message,
            {
                "order_id": order_id,
                "retry_queue_size": len(self.retry_queue),
                "retry_queue_maxsize": self.MAX_RETRY_QUEUE_SIZE,
                "error_message": error_message,
            },
        )
        return {"success": False, "message": "重试队列已满，订单已被拒绝"}

    def _add_to_retry_queue(
        self, order_id: str, retry_count: int, error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """添加订单到重试队列"""
        with self.retry_lock:
            # 检查是否已在重试队列中
            existing = next(
                (r for r in self.retry_queue if r.order_id == order_id), None
            )
            if existing:
                existing.retry_count += 1
                existing.last_attempt_time = time.time()
                # 递增重试间隔：1s, 5s, 30s
                retry_intervals = [1, 5, 30]
                interval_index = min(existing.retry_count - 1, len(retry_intervals) - 1)
                next_interval = retry_intervals[interval_index]
                existing.next_retry_time = time.time() + next_interval
                existing.error_message = error_message
            else:
                if len(self.retry_queue) >= self.MAX_RETRY_QUEUE_SIZE:
                    return self._reject_retry_queue_entry(order_id, error_message)

                # 递增重试间隔：1s, 5s, 30s
                retry_intervals = [1, 5, 30]
                interval_index = min(retry_count, len(retry_intervals) - 1)
                next_interval = retry_intervals[interval_index]

                retry_record = PaymentRetryRecord(
                    order_id=order_id,
                    retry_count=retry_count,
                    first_attempt_time=time.time(),
                    last_attempt_time=time.time(),
                    next_retry_time=time.time() + next_interval,
                    error_message=error_message,
                    max_retries=self.max_retries,
                )
                self.retry_queue.append(retry_record)

            with self.stats_lock:
                self.stats["retried"] += 1

            logger.info(
                f"订单已加入重试队列: {order_id}, "
                f"重试次数: {retry_count + 1}/{self.max_retries}"
            )
            return {
                "success": True,
                "message": "订单已加入重试队列",
                "retry_count": retry_count + 1,
            }

    def process_order(self, order_id: str) -> bool:
        """处理单个订单"""
        try:
            # 该监控器通过后台线程调用此方法；这里显式创建并关闭线程私有事件循环，
            # 避免 asyncio.run() 在已有事件循环上下文中抛错，也避免复用外部事件循环。
            self._run_payment_success_handler(order_id)
            with self.stats_lock:
                self.stats["processed"] += 1
            logger.info(f"✅ 订单处理成功: {order_id}")
            return True
        except Exception as e:
            with self.stats_lock:
                self.stats["failed"] += 1
            logger.error(f"❌ 订单处理失败: {order_id}, 错误: {e}")

            # 添加到重试队列
            retry_count = self._get_retry_count(order_id)
            if retry_count < self.max_retries:
                self._add_to_retry_queue(order_id, retry_count, str(e))
            else:
                alert_msg = f"订单 {order_id} 重试次数已耗尽"
                logger.critical(f"订单重试次数已耗尽: {order_id}, 需要人工介入处理")
                self.record_alert(
                    "retry_exhausted",
                    "critical",
                    alert_msg,
                    {"order_id": order_id, "retry_count": retry_count},
                )

            return False

    def _get_retry_count(self, order_id: str) -> int:
        """获取订单的重试次数"""
        with self.retry_lock:
            record = next((r for r in self.retry_queue if r.order_id == order_id), None)
            return record.retry_count if record else 0

    def process_retry_queue(self):
        """处理重试队列"""
        current_time = time.time()
        retries_to_process = []

        with self.retry_lock:
            # 找出需要重试的订单
            remaining_retries = []
            for retry_record in self.retry_queue:
                if current_time >= retry_record.next_retry_time:
                    if retry_record.retry_count < retry_record.max_retries:
                        retries_to_process.append(retry_record)
                        remaining_retries.append(retry_record)
                    else:
                        # 重试次数已耗尽，记录告警
                        alert_msg = f"订单 {retry_record.order_id} 重试次数已耗尽"
                        logger.critical(alert_msg)
                        self.record_alert(
                            "retry_exhausted",
                            "critical",
                            alert_msg,
                            {
                                "order_id": retry_record.order_id,
                                "retry_count": retry_record.retry_count,
                            },
                        )
                else:
                    remaining_retries.append(retry_record)

            self.retry_queue = remaining_retries

        # 处理需要重试的订单
        for retry_record in retries_to_process:
            logger.info(
                f"重试处理订单: {retry_record.order_id}, "
                f"第 {retry_record.retry_count + 1} 次重试"
            )
            success = self.process_order(retry_record.order_id)
            if success:
                # 从重试队列中移除
                with self.retry_lock:
                    self.retry_queue = [
                        r
                        for r in self.retry_queue
                        if r.order_id != retry_record.order_id
                    ]

    def check_queue_status(self):
        """检查队列状态并触发告警"""
        queue_size = len(self.retry_queue)
        alert_level = None
        alert_message = ""

        if queue_size >= self.queue_critical_threshold:
            alert_level = "critical"
            alert_message = (
                f"严重告警：支付重试积压过高 ({queue_size}/{self.queue_maxsize})"
            )
        elif queue_size >= self.queue_warning_threshold:
            alert_level = "warning"
            alert_message = (
                f"警告：支付重试积压接近满载 ({queue_size}/{self.queue_maxsize})"
            )

        if alert_level and alert_message:
            self.record_alert(
                "queue_full",
                alert_level,
                alert_message,
                {
                    "queue_size": queue_size,
                    "queue_maxsize": self.queue_maxsize,
                    "retry_queue_size": len(self.retry_queue),
                },
            )

    def check_failure_rate(self):
        """检查失败率并触发告警"""
        with self.stats_lock:
            total = self.stats["processed"] + self.stats["failed"]
            if total == 0:
                return

            failure_rate = self.stats["failed"] / total
            if failure_rate > 0.1:  # 失败率超过10%
                alert_level = "critical" if failure_rate > 0.3 else "warning"
                self.record_alert(
                    "high_failure_rate",
                    alert_level,
                    f"支付处理失败率过高: {failure_rate * 100:.1f}%",
                    {
                        "failure_rate": failure_rate,
                        "processed": self.stats["processed"],
                        "failed": self.stats["failed"],
                    },
                )

    def record_alert(
        self, alert_type: str, level: str, message: str, alert_stats: Dict[str, Any]
    ):
        """记录告警"""
        with self.alert_lock:
            # 检查是否已有未解决的相同告警
            existing_unresolved = [
                a
                for a in self.alerts
                if (not a.resolved and a.alert_type == alert_type and a.level == level)
            ]
            if existing_unresolved:
                existing_unresolved[0].timestamp = time.time()
                existing_unresolved[0].message = message
                existing_unresolved[0].stats = alert_stats
                return

            # 创建新告警
            alert = PaymentAlert(
                timestamp=time.time(),
                alert_type=alert_type,
                level=level,
                message=message,
                stats=alert_stats,
            )
            self.alerts.append(alert)

            # 只保留最近100条告警
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-100:]

            # 记录日志
            if level == "critical":
                logger.critical(message)
            else:
                logger.warning(message)

            # 发送告警通知
            PaymentCallbackEnhanced.send_alert_notification(alert)

    @staticmethod
    def send_alert_notification(alert: PaymentAlert):
        """发送告警通知"""
        try:
            alert_file = "payment_alerts.log"
            with open(alert_file, "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.fromtimestamp(alert.timestamp).isoformat()} "
                    f"[{alert.level.upper()}] [{alert.alert_type}] "
                    f"{alert.message}\n"
                )
        except Exception as e:
            logger.error(f"写入告警日志失败: {e}")

    def check_and_monitor(self):
        """执行检查和监控"""
        # 检查队列状态
        self.check_queue_status()

        # 检查失败率
        self.check_failure_rate()

        # 处理重试队列
        self.process_retry_queue()

        with self.stats_lock:
            self.stats["last_check_time"] = time.time()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.stats_lock:
            return {
                **self.stats,
                "queue_size": len(self.retry_queue),
                "retry_queue_size": len(self.retry_queue),
                "queue_maxsize": self.queue_maxsize,
            }

    def get_recent_alerts(
        self, limit: int = 10, unresolved_only: bool = False
    ) -> List[Dict[str, Any]]:
        """获取最近的告警"""
        with self.alert_lock:
            alert_list = self.alerts
            if unresolved_only:
                alert_list = [a for a in alert_list if not a.resolved]
            alert_list = sorted(alert_list, key=lambda x: x.timestamp, reverse=True)[
                :limit
            ]

            return [
                {
                    "timestamp": a.timestamp,
                    "alert_type": a.alert_type,
                    "level": a.level,
                    "message": a.message,
                    "stats": a.stats,
                    "resolved": a.resolved,
                    "resolved_at": a.resolved_at,
                }
                for a in alert_list
            ]

    def start_monitoring(self):
        """启动监控线程"""
        if self.monitoring:
            logger.warning("监控已在运行中")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="PaymentCallbackMonitor"
        )
        self.monitor_thread.start()
        logger.info("支付回调监控已启动")

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("支付回调监控已停止")

    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                self.check_and_monitor()
            except Exception as e:
                logger.error(f"监控检查异常: {e}")

            # 等待下次检查
            time.sleep(self.check_interval)


# 全局实例
_global_payment_monitor: Optional[PaymentCallbackEnhanced] = None
_payment_monitor_lock = threading.Lock()


def get_payment_callback_monitor() -> PaymentCallbackEnhanced:
    """获取全局支付回调监控实例"""
    global _global_payment_monitor
    with _payment_monitor_lock:
        if _global_payment_monitor is None:
            _global_payment_monitor = PaymentCallbackEnhanced()
            _global_payment_monitor.start_monitoring()
        return _global_payment_monitor


if __name__ == "__main__":
    # 测试支付回调监控
    print("测试增强支付回调监控...")

    monitor = PaymentCallbackEnhanced(
        queue_maxsize=100,
        queue_warning_threshold=50,
        queue_critical_threshold=80,
        check_interval=10,
    )

    monitor.start_monitoring()

    # 模拟加入订单
    for i in range(5):
        monitor.enqueue_order(f"TEST_ORDER_{i}")

    # 等待处理
    time.sleep(15)

    # 获取统计
    stats = monitor.get_stats()
    print(f"统计信息: {stats}")

    # 获取告警
    alerts = monitor.get_recent_alerts()
    print(f"最近告警: {len(alerts)} 条")

    monitor.stop_monitoring()
    print("✅ 支付回调监控测试完成")
