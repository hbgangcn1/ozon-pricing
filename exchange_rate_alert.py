# -*- coding: utf-8 -*-
"""
汇率服务监控告警模块
监控汇率获取失败并发送告警
"""

import os
import time
import threading
from datetime import datetime
from typing import Optional, Dict, List, Callable

try:
    from logger_config import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class ExchangeRateAlert:
    """汇率服务告警管理器"""

    # 告警配置（类级别默认值）
    _DEFAULT_FAILURE_THRESHOLD = 3  # 连续失败次数阈值
    _DEFAULT_ALERT_COOLDOWN = 300  # 告警冷却时间（秒）
    HEALTH_CHECK_INTERVAL = 60  # 健康检查间隔（秒）

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._failure_count = 0
        self._last_success_time: Optional[float] = None
        self._last_alert_time: Optional[float] = None
        self._alert_handlers: List[Callable[[Dict], None]] = []
        self._alert_history: List[Dict] = []
        self._max_history = 100
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._stats_lock = threading.Lock()

        # 从环境变量读取配置（实例级别）
        self._failure_threshold = int(
            os.getenv('EXCHANGE_ALERT_THRESHOLD',
                      str(self._DEFAULT_FAILURE_THRESHOLD))
        )
        self._alert_cooldown = int(
            os.getenv('EXCHANGE_ALERT_COOLDOWN',
                      str(self._DEFAULT_ALERT_COOLDOWN))
        )

        self._initialized = True
        logger.info("汇率告警管理器初始化完成")

    def register_alert_handler(
        self, handler: Callable[[Dict], None]
    ) -> None:
        """
        注册告警处理器

        Args:
            handler: 告警回调函数，接收告警信息字典
        """
        if handler not in self._alert_handlers:
            self._alert_handlers.append(handler)
            handler_name = getattr(handler, '__name__', repr(handler))
            logger.info(f"已注册告警处理器: {handler_name}")

    def unregister_alert_handler(
        self, handler: Callable[[Dict], None]
    ) -> None:
        """移除告警处理器"""
        if handler in self._alert_handlers:
            self._alert_handlers.remove(handler)

    def record_success(self) -> None:
        """记录汇率获取成功"""
        with self._stats_lock:
            self._failure_count = 0
            self._last_success_time = time.time()
            logger.debug("汇率获取成功，重置失败计数")

    def record_failure(self, error_message: str, source: str = "") -> None:
        """
        记录汇率获取失败

        Args:
            error_message: 错误信息
            source: 失败的数据源名称
        """
        with self._stats_lock:
            self._failure_count += 1
            logger.warning(
                f"汇率获取失败 ({self._failure_count}/{self._failure_threshold}): "
                f"{source} - {error_message}"
            )

            if self._failure_count >= self._failure_threshold:
                self._trigger_alert(error_message, source)

    def _trigger_alert(self, error_message: str, source: str) -> None:
        """触发告警"""
        current_time = time.time()

        # 检查冷却时间
        if (self._last_alert_time and
                current_time - self._last_alert_time < self._alert_cooldown):
            logger.debug("告警冷却中，跳过本次告警")
            return

        self._last_alert_time = current_time

        alert_info = {
            'type': 'EXCHANGE_RATE_FAILURE',
            'level': 'HIGH',
            'message': f'汇率服务连续失败 {self._failure_count} 次',
            'error': error_message,
            'source': source,
            'timestamp': datetime.now().isoformat(),
            'last_success': (
                datetime.fromtimestamp(self._last_success_time).isoformat()
                if self._last_success_time else None
            ),
            'failure_count': self._failure_count,
        }

        # 记录到历史
        self._alert_history.append(alert_info)
        if len(self._alert_history) > self._max_history:
            self._alert_history = self._alert_history[-self._max_history:]

        # 调用所有注册的处理器
        for handler in self._alert_handlers:
            try:
                handler(alert_info)
            except Exception as e:
                handler_name = getattr(handler, '__name__', repr(handler))
                logger.error(f"告警处理器执行失败: {handler_name} - {e}")

        # 默认日志告警
        logger.error(
            f"🚨 汇率服务告警: {alert_info['message']} | "
            f"最后成功: {alert_info['last_success']}"
        )

    def get_status(self) -> Dict:
        """获取当前状态"""
        with self._stats_lock:
            return {
                'healthy': self._failure_count < self._failure_threshold,
                'failure_count': self._failure_count,
                'failure_threshold': self._failure_threshold,
                'last_success_time': (
                    datetime.fromtimestamp(self._last_success_time).isoformat()
                    if self._last_success_time else None
                ),
                'last_alert_time': (
                    datetime.fromtimestamp(self._last_alert_time).isoformat()
                    if self._last_alert_time else None
                ),
                'recent_alerts': self._alert_history[-5:],
            }

    def get_alert_history(self, limit: int = 20) -> List[Dict]:
        """获取告警历史"""
        return self._alert_history[-limit:]

    def reset(self) -> None:
        """重置状态（用于测试或手动恢复）"""
        with self._stats_lock:
            self._failure_count = 0
            logger.info("汇率告警状态已重置")

    def reset_for_testing(
        self,
        clear_history: bool = True,
        clear_handlers: bool = True,
        failure_threshold: Optional[int] = None,
        alert_cooldown: Optional[int] = None
    ) -> None:
        """
        重置状态用于测试（扩展版本）

        Args:
            clear_history: 是否清除告警历史
            clear_handlers: 是否清除告警处理器
            failure_threshold: 设置新的失败阈值
            alert_cooldown: 设置新的告警冷却时间
        """
        self.reset()
        if clear_history:
            self._alert_history.clear()
        if clear_handlers:
            self._alert_handlers.clear()
        self._last_alert_time = None
        self._last_success_time = None
        if failure_threshold is not None:
            self._failure_threshold = failure_threshold
        if alert_cooldown is not None:
            self._alert_cooldown = alert_cooldown

    def set_config_for_testing(
        self, failure_threshold: int, alert_cooldown: int
    ) -> None:
        """设置测试配置"""
        self._failure_threshold = failure_threshold
        self._alert_cooldown = alert_cooldown

    def reinitialize_for_testing(self) -> None:
        """重新初始化实例用于测试（允许重新读取环境变量）"""
        self._initialized = False
        self.__init__()

    def start_monitor(self) -> None:
        """启动后台健康监控"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ExchangeRateMonitor"
        )
        self._monitor_thread.start()
        logger.info("汇率健康监控线程已启动")

    def stop_monitor(self) -> None:
        """停止后台监控"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            logger.info("汇率健康监控线程已停止")

    def _monitor_loop(self) -> None:
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                # 检查是否长时间未成功获取汇率
                if self._last_success_time:
                    elapsed = time.time() - self._last_success_time
                    if elapsed > self.HEALTH_CHECK_INTERVAL * 5:
                        self._trigger_alert(
                            f"汇率服务已超过 {int(elapsed)} 秒未更新",
                            "health_check"
                        )
            except Exception as e:
                logger.error(f"健康监控异常: {e}")

            self._stop_event.wait(self.HEALTH_CHECK_INTERVAL)


# 默认告警处理器示例
def log_alert_handler(alert_info: Dict) -> None:
    """日志告警处理器"""
    logger.error(
        f"[告警] {alert_info['type']}: {alert_info['message']}"
    )


def file_alert_handler(alert_info: Dict) -> None:
    """文件告警处理器"""
    alert_file = os.path.join(
        os.path.dirname(__file__),
        "exchange_rate_alerts.log"
    )
    try:
        with open(alert_file, 'a', encoding='utf-8') as f:
            f.write(
                f"{alert_info['timestamp']} | {alert_info['level']} | "
                f"{alert_info['message']} | {alert_info['error']}\n"
            )
    except IOError as e:
        logger.error(f"写入告警文件失败: {e}")


# 单例获取函数
def get_exchange_rate_alert() -> ExchangeRateAlert:
    """获取汇率告警管理器单例"""
    return ExchangeRateAlert()


# 便捷函数
def record_exchange_success() -> None:
    """记录汇率获取成功"""
    get_exchange_rate_alert().record_success()


def record_exchange_failure(error: str, source: str = "") -> None:
    """记录汇率获取失败"""
    get_exchange_rate_alert().record_failure(error, source)
