# -*- coding: utf-8 -*-
"""
增强数据库连接监控和告警系统
解决高优先级问题：数据库连接泄露风险
"""

import time
import threading
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ConnectionAlert:
    """连接告警记录"""
    timestamp: float
    level: str  # 'warning', 'critical'
    message: str
    stats: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[float] = None


class ConnectionMonitorEnhanced:
    """增强连接监控器"""

    def __init__(
        self,
        warning_threshold: int = 5,  # 降低警告阈值
        critical_threshold: int = 20,  # 降低严重阈值
        check_interval: int = 60,  # 检查间隔（秒）
        leak_threshold: int = 300,  # 连接泄露阈值（秒）
        auto_recycle: bool = True  # 启用自动回收
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.check_interval = check_interval
        self.leak_threshold = leak_threshold
        self.auto_recycle = auto_recycle
        self.alerts: List[ConnectionAlert] = []
        self.alert_lock = threading.Lock()
        self.last_check_time = 0.0
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

    @staticmethod
    def get_connection_stats() -> Dict[str, Any]:
        """获取连接统计信息"""
        try:
            from db_utils import get_connection_stats
            return get_connection_stats()
        except ImportError:
            try:
                from enhanced_connection_manager import get_connection_stats
                return get_connection_stats()
            except ImportError:
                logger.warning("无法获取连接统计信息")
                return {'error': '无法获取连接统计信息'}

    @staticmethod
    def detect_leaks() -> List[Dict[str, Any]]:
        """检测连接泄露"""
        leaks = []
        # 先定义占位函数，满足静态分析要求

        def _default_get_connection_pool():
            return None

        try:
            from enhanced_connection_manager import (
                get_connection_pool  # type: ignore
            )
        except ImportError:
            logger.warning("无法使用增强连接管理器检测泄露")
            # 使用默认占位函数
            get_connection_pool: Callable = _default_get_connection_pool

        try:
            pool = get_connection_pool()
            if pool is not None:
                leaks = pool.detect_leaks()
        except (AttributeError, TypeError, Exception) as e:
            logger.error(f"检测连接泄露时出错: {e}")
            leaks = []
        return leaks

    def check_and_alert(self) -> Dict[str, Any]:
        """检查连接状态并触发告警"""
        stats = ConnectionMonitorEnhanced.get_connection_stats()
        active_connections = stats.get('active_connections', 0)
        leaks = ConnectionMonitorEnhanced.detect_leaks()
        leak_count = len(leaks)

        # 自动回收机制：如果启用了自动回收且检测到泄露
        if self.auto_recycle and leak_count > 0:
            self._auto_recycle_connections(leaks)

        alert_level: Optional[str] = None
        alert_message = ""

        # 检查连接数阈值
        if active_connections > self.critical_threshold:
            alert_level = 'critical'
            alert_message = (
                f"严重告警：活跃连接数 {active_connections} 超过严重阈值 "
                f"{self.critical_threshold}"
            )
        elif active_connections > self.warning_threshold:
            alert_level = 'warning'
            alert_message = (
                f"警告：活跃连接数 {active_connections} 超过警告阈值 "
                f"{self.warning_threshold}"
            )

        # 检查连接泄露
        if leak_count > 0:
            if alert_level != 'critical':
                alert_level = 'warning'
            leak_msg = f"检测到 {leak_count} 个连接泄露"
            if alert_message:
                alert_message += f"，{leak_msg}"
            else:
                alert_message = leak_msg

        # 记录告警
        if alert_level is not None and alert_message:
            # alert_level 此时已经确定是 str 类型（不是 None）
            self.record_alert(alert_level, alert_message, stats, leaks)

        # 检查告警是否已解决
        self.check_alert_resolution(stats)

        return {
            'status': alert_level or 'normal',
            'active_connections': active_connections,
            'leak_count': leak_count,
            'alert_level': alert_level,
            'alert_message': alert_message,
            'stats': stats
        }

    def record_alert(
        self,
        level: str,
        message: str,
        stats: Dict[str, Any],
        leaks: List[Dict[str, Any]]
    ):
        """记录告警"""
        with self.alert_lock:
            # 检查是否已有未解决的相同告警
            existing_unresolved = [
                a for a in self.alerts
                if not a.resolved and a.level == level
            ]
            if existing_unresolved:
                # 更新最新告警时间
                existing_unresolved[0].timestamp = time.time()
                existing_unresolved[0].stats = stats
                return

            # 创建新告警
            alert = ConnectionAlert(
                timestamp=time.time(),
                level=level,
                message=message,
                stats={**stats, 'leaks': leaks}
            )
            self.alerts.append(alert)

            # 只保留最近100条告警
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-100:]

            # 记录日志
            if level == 'critical':
                logger.critical(message)
            else:
                logger.warning(message)

            # 这里可以添加发送告警通知的逻辑
            # 例如：发送邮件、短信、企业微信等
            ConnectionMonitorEnhanced.send_alert_notification(alert)

    def check_alert_resolution(self, current_stats: Dict[str, Any]):
        """检查告警是否已解决"""
        with self.alert_lock:
            active_connections = current_stats.get('active_connections', 0)
            leaks = ConnectionMonitorEnhanced.detect_leaks()
            leak_count = len(leaks)

            # 检查告警是否已解决
            for alert in self.alerts:
                if alert.resolved:
                    continue

                # 检查连接数告警
                if alert.level == 'critical':
                    if active_connections <= self.warning_threshold:
                        alert.resolved = True
                        alert.resolved_at = time.time()
                        logger.info(
                            f"告警已解决：{alert.message} -> "
                            f"当前连接数: {active_connections}"
                        )
                elif alert.level == 'warning':
                    if (active_connections <= self.warning_threshold and
                            leak_count == 0):
                        alert.resolved = True
                        alert.resolved_at = time.time()
                        logger.info(
                            f"告警已解决：{alert.message} -> "
                            f"当前连接数: {active_connections}, "
                            f"泄露数: {leak_count}"
                        )

    @staticmethod
    def _auto_recycle_connections(leaks: List[Dict[str, Any]]):
        """自动回收泄露的连接"""
        if not leaks:
            return

        recycled_count: int = 0
        try:
            # 尝试从增强连接管理器回收连接
            try:
                from enhanced_connection_manager import (
                    recycle_leaked_connections  # type: ignore
                )
                if callable(recycle_leaked_connections):
                    result = recycle_leaked_connections(leaks)
                    if isinstance(result, int):
                        recycled_count = result
                    logger.info(
                        f"自动回收了 {recycled_count} 个泄露的连接"
                    )
            except (ImportError, AttributeError):
                # 如果没有增强连接管理器，尝试直接关闭连接
                for leak in leaks:
                    try:
                        conn = leak.get('connection')
                        if conn and hasattr(conn, 'close'):
                            conn.close()
                            recycled_count = recycled_count + 1
                    except Exception as e:
                        logger.warning(f"回收连接失败: {e}")
        except Exception as e:
            logger.error(f"自动回收连接时出错: {e}")

        if recycled_count > 0:
            logger.info(
                f"✅ 自动回收完成：成功回收 {recycled_count}/{len(leaks)} "
                f"个泄露的连接"
            )

    @staticmethod
    def send_alert_notification(alert: ConnectionAlert):
        """发送告警通知（可扩展）"""
        # 这里可以实现发送邮件、短信、企业微信等通知
        # 示例：写入文件或发送到监控系统
        try:
            alert_file = 'connection_alerts.log'
            with open(alert_file, 'a', encoding='utf-8') as f:
                f.write(
                    f"{datetime.fromtimestamp(alert.timestamp).isoformat()} "
                    f"[{alert.level.upper()}] {alert.message}\n"
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
                    'level': a.level,
                    'message': a.message,
                    'resolved': a.resolved,
                    'resolved_at': a.resolved_at,
                    'stats': a.stats
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
            name="ConnectionMonitor"
        )
        self.monitor_thread.start()
        logger.info("连接监控已启动")

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("连接监控已停止")

    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                self.check_and_alert()
                self.last_check_time = time.time()
            except Exception as e:
                logger.error(f"监控检查异常: {e}")

            # 等待下次检查
            time.sleep(self.check_interval)

    def get_monitor_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        return {
            'monitoring': self.monitoring,
            'last_check_time': self.last_check_time,
            'check_interval': self.check_interval,
            'warning_threshold': self.warning_threshold,
            'critical_threshold': self.critical_threshold,
            'total_alerts': len(self.alerts),
            'unresolved_alerts': len(
                [a for a in self.alerts if not a.resolved]
            )
        }


# 全局监控实例
_global_monitor: Optional[ConnectionMonitorEnhanced] = None
_monitor_lock = threading.Lock()


def get_connection_monitor() -> ConnectionMonitorEnhanced:
    """获取全局连接监控实例"""
    global _global_monitor
    with _monitor_lock:
        if _global_monitor is None:
            _global_monitor = ConnectionMonitorEnhanced()
            _global_monitor.start_monitoring()
        return _global_monitor


if __name__ == "__main__":
    # 测试连接监控
    print("测试增强连接监控...")

    monitor = ConnectionMonitorEnhanced(
        warning_threshold=5,
        critical_threshold=10,
        check_interval=10
    )

    monitor.start_monitoring()

    # 等待几次检查
    time.sleep(15)

    # 获取状态
    status = monitor.get_monitor_status()
    print(f"监控状态: {status}")

    # 获取告警
    alerts = monitor.get_recent_alerts()
    print(f"最近告警: {len(alerts)} 条")

    monitor.stop_monitoring()
    print("✅ 连接监控测试完成")
