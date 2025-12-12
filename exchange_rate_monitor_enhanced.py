# -*- coding: utf-8 -*-
"""
增强汇率监控和告警系统
解决高优先级问题：汇率API依赖风险
"""

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
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)


@dataclass
class ExchangeRateAlert:
    """汇率告警记录"""
    timestamp: float
    alert_type: str  # 'api_failure', 'rate_change', 'stale_data'
    level: str  # 'warning', 'critical'
    message: str
    current_rate: Optional[float] = None
    previous_rate: Optional[float] = None
    resolved: bool = False
    resolved_at: Optional[float] = None


class ExchangeRateMonitorEnhanced:
    """增强汇率监控器"""

    def __init__(
        self,
        rate_change_threshold: float = 0.05,  # 5%变化阈值（告警）
        deprecated_data_threshold: int = 7200,  # 2小时数据过期阈值
        check_interval: int = 300  # 5分钟检查一次
    ):
        self.rate_change_threshold = rate_change_threshold
        self.deprecated_data_threshold = deprecated_data_threshold
        self.check_interval = check_interval
        self.alerts: List[ExchangeRateAlert] = []
        self.alert_lock = threading.Lock()
        self.last_rate: Optional[float] = None
        self.last_rate_time: float = 0.0
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.api_failure_count = 0
        self.max_api_failures = 3

    @staticmethod
    def get_current_rate() -> Dict[str, Any]:
        """获取当前汇率信息"""
        try:
            from exchange_service import ExchangeRateService
            service = ExchangeRateService()
            rate = service.get_cached_rate()
            # 获取最后更新时间
            last_update = getattr(service, '_last', 0)
            return {
                'rate': rate,
                'last_update': last_update,
                'age': time.time() - last_update if last_update > 0 else 0
            }
        except Exception as e:
            logger.error(f"获取汇率失败: {e}")
            return {
                'rate': None,
                'last_update': 0,
                'age': 0,
                'error': str(e)
            }

    @staticmethod
    def get_provider_status() -> Dict[str, Any]:
        """获取汇率提供者状态"""
        try:
            from enhanced_exchange_service import get_enhanced_exchange_service
            service = get_enhanced_exchange_service()
            return service.get_provider_status()
        except ImportError:
            # 降级到基础服务
            return {'status': 'unknown'}

    def check_and_alert(self) -> Dict[str, Any]:
        """检查汇率状态并触发告警"""
        rate_info = ExchangeRateMonitorEnhanced.get_current_rate()
        current_rate = rate_info.get('rate')
        rate_age = rate_info.get('age', 0)

        alerts_triggered = []

        # 检查1：API失败
        provider_status = ExchangeRateMonitorEnhanced.get_provider_status()
        failed_providers = [
            name for name, provider_info in provider_status.items()
            if not provider_info.get('available', True)
        ]

        if len(failed_providers) >= self.max_api_failures:
            alert = ExchangeRateAlert(
                timestamp=time.time(),
                alert_type='api_failure',
                level='critical',
                message=(
                    f"严重告警：{len(failed_providers)} 个汇率API失败，"
                    f"失败提供者: {', '.join(failed_providers)}"
                ),
                current_rate=current_rate
            )
            self.record_alert(alert)
            alerts_triggered.append(alert)

        # 检查2：数据过期
        if rate_age > self.deprecated_data_threshold:
            alert = ExchangeRateAlert(
                timestamp=time.time(),
                alert_type='stale_data',
                level='warning' if rate_age < 14400 else 'critical',  # 4小时
                message=(
                    f"汇率数据过期：数据已存在 {rate_age / 3600:.1f} 小时，"
                    f"超过阈值 {self.deprecated_data_threshold / 3600:.1f} 小时"
                ),
                current_rate=current_rate
            )
            self.record_alert(alert)
            alerts_triggered.append(alert)

        # 检查3：汇率变化过大
        if current_rate and self.last_rate:
            rate_change = abs(current_rate - self.last_rate) / self.last_rate
            if rate_change > self.rate_change_threshold:
                alert = ExchangeRateAlert(
                    timestamp=time.time(),
                    alert_type='rate_change',
                    level=('warning' if rate_change < 0.1
                           else 'critical'),  # 10%
                    message=(
                        f"汇率变化过大：从 {self.last_rate:.5f} 变化到 "
                        f"{current_rate:.5f}，变化幅度 {rate_change * 100:.2f}%"
                    ),
                    current_rate=current_rate,
                    previous_rate=self.last_rate
                )
                self.record_alert(alert)
                alerts_triggered.append(alert)

        # 更新记录
        if current_rate:
            self.last_rate = current_rate
            self.last_rate_time = time.time()

        return {
            'status': 'normal' if not alerts_triggered else 'alert',
            'current_rate': current_rate,
            'rate_age': rate_age,
            'alerts_triggered': len(alerts_triggered),
            'provider_status': provider_status
        }

    def record_alert(self, alert: ExchangeRateAlert):
        """记录告警"""
        with self.alert_lock:
            # 检查是否已有未解决的相同告警
            existing_unresolved = [
                a for a in self.alerts
                if (not a.resolved and
                    a.alert_type == alert.alert_type and
                    a.level == alert.level)
            ]
            if existing_unresolved:
                # 更新最新告警时间
                existing_unresolved[0].timestamp = time.time()
                existing_unresolved[0].message = alert.message
                existing_unresolved[0].current_rate = alert.current_rate
                return

            # 创建新告警
            self.alerts.append(alert)

            # 只保留最近100条告警
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-100:]

            # 记录日志
            if alert.level == 'critical':
                logger.critical(alert.message)
            else:
                logger.warning(alert.message)

            # 发送告警通知
            ExchangeRateMonitorEnhanced.send_alert_notification(alert)

    def check_alert_resolution(self, rate_info: Dict[str, Any]):
        """检查告警是否已解决"""
        with self.alert_lock:
            rate_age = rate_info.get('age', 0)

            # 检查告警是否已解决
            for alert in self.alerts:
                if alert.resolved:
                    continue

                # API失败告警
                if alert.alert_type == 'api_failure':
                    provider_status = (
                        ExchangeRateMonitorEnhanced.get_provider_status()
                    )
                    failed_count = sum(
                        1 for provider_info in provider_status.values()
                        if not provider_info.get('available', True)
                    )
                    if failed_count < self.max_api_failures:
                        alert.resolved = True
                        alert.resolved_at = time.time()
                        logger.info(f"告警已解决：{alert.message}")

                # 数据过期告警
                elif alert.alert_type == 'stale_data':
                    if rate_age < self.deprecated_data_threshold:
                        alert.resolved = True
                        alert.resolved_at = time.time()
                        logger.info(f"告警已解决：{alert.message}")

    @staticmethod
    def send_alert_notification(alert: ExchangeRateAlert):
        """发送告警通知"""
        try:
            alert_file = 'exchange_rate_alerts.log'
            with open(alert_file, 'a', encoding='utf-8') as f:
                f.write(
                    f"{datetime.fromtimestamp(alert.timestamp).isoformat()} "
                    f"[{alert.level.upper()}] [{alert.alert_type}] "
                    f"{alert.message}\n"
                )
        except Exception as e:
            logger.error(f"写入告警日志失败: {e}")

    def get_recent_alerts(
        self,
        limit: int = 10,
        unresolved_only: bool = False
    ) -> List[Dict[str, Any]]:
        """获取最近的告警"""
        with self.alert_lock:
            alert_list = self.alerts
            if unresolved_only:
                alert_list = [a for a in alert_list if not a.resolved]
            alert_list = sorted(
                alert_list,
                key=lambda x: x.timestamp,
                reverse=True
            )[:limit]

            return [
                {
                    'timestamp': a.timestamp,
                    'alert_type': a.alert_type,
                    'level': a.level,
                    'message': a.message,
                    'current_rate': a.current_rate,
                    'previous_rate': a.previous_rate,
                    'resolved': a.resolved,
                    'resolved_at': a.resolved_at
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
            target=self._monitor_loop,
            daemon=True,
            name="ExchangeRateMonitor"
        )
        self.monitor_thread.start()
        logger.info("汇率监控已启动")

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("汇率监控已停止")

    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                check_result = self.check_and_alert()
                self.check_alert_resolution(check_result)
            except Exception as e:
                logger.error(f"监控检查异常: {e}")

            # 等待下次检查
            time.sleep(self.check_interval)

    def get_monitor_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        return {
            'monitoring': self.monitoring,
            'check_interval': self.check_interval,
            'rate_change_threshold': self.rate_change_threshold,
            'deprecated_data_threshold': self.deprecated_data_threshold,
            'total_alerts': len(self.alerts),
            'unresolved_alerts': len(
                [a for a in self.alerts if not a.resolved]
            ),
            'last_rate': self.last_rate,
            'last_rate_time': self.last_rate_time
        }

    @staticmethod
    def manual_update_rate(rub_cny: float, usd_cny: float = 7.2):
        """手动更新汇率（管理员接口）"""
        try:
            from enhanced_exchange_service import EnhancedExchangeRateService
            EnhancedExchangeRateService.update_fallback_rates(rub_cny, usd_cny)
            logger.info(f"手动更新汇率成功: RUB/CNY={rub_cny}, USD/CNY={usd_cny}")
            return {'success': True, 'message': '汇率更新成功'}
        except Exception as e:
            logger.error(f"手动更新汇率失败: {e}")
            return {'success': False, 'message': str(e)}


# 全局监控实例
_global_rate_monitor: Optional[ExchangeRateMonitorEnhanced] = None
_rate_monitor_lock = threading.Lock()


def get_exchange_rate_monitor() -> ExchangeRateMonitorEnhanced:
    """获取全局汇率监控实例"""
    global _global_rate_monitor
    with _rate_monitor_lock:
        if _global_rate_monitor is None:
            _global_rate_monitor = ExchangeRateMonitorEnhanced()
            _global_rate_monitor.start_monitoring()
        return _global_rate_monitor


if __name__ == "__main__":
    # 测试汇率监控
    print("测试增强汇率监控...")

    monitor = ExchangeRateMonitorEnhanced(
        rate_change_threshold=0.05,
        deprecated_data_threshold=3600,
        check_interval=60
    )

    monitor.start_monitoring()

    # 等待几次检查
    time.sleep(70)

    # 获取状态
    status = monitor.get_monitor_status()
    print(f"监控状态: {status}")

    # 获取告警
    alerts = monitor.get_recent_alerts()
    print(f"最近告警: {len(alerts)} 条")

    monitor.stop_monitoring()
    print("✅ 汇率监控测试完成")
