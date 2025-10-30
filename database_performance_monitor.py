# -*- coding: utf-8 -*-
"""
数据库性能监控模块
提供数据库连接池监控、性能指标收集和告警功能
"""

import time
import threading
from typing import Dict, List, Any
from datetime import datetime

try:
    from .db_utils import get_connection_stats
except ImportError:
    from db_utils import get_connection_stats


class PerformanceConfig:
    """性能监控配置"""
    # 连接池监控阈值
    CONNECTION_WARNING_THRESHOLD = 15  # 连接数警告阈值
    CONNECTION_CRITICAL_THRESHOLD = 25  # 连接数严重阈值

    # 查询性能阈值（毫秒）
    QUERY_WARNING_THRESHOLD = 1000  # 查询警告阈值
    QUERY_CRITICAL_THRESHOLD = 5000  # 查询严重阈值

    # 缓存监控阈值
    CACHE_HIT_RATE_WARNING = 0.7  # 缓存命中率警告阈值
    CACHE_HIT_RATE_CRITICAL = 0.5  # 缓存命中率严重阈值

    # 监控间隔（秒）
    MONITORING_INTERVAL = 30  # 监控间隔
    ALERT_COOLDOWN = 300  # 告警冷却时间


class DatabasePerformanceMonitor:
    """数据库性能监控器"""

    def __init__(self):
        self.metrics = {
            'connection_pool': {},
            'query_performance': [],
            'cache_stats': {},
            'alerts': []
        }
        self.monitoring = False
        self.monitor_thread = None
        self.last_alert_time = {}

    def start_monitoring(self):
        """开始性能监控"""
        if self.monitoring:
            print("监控已在运行中")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.monitor_thread.start()
        print("数据库性能监控已启动")

    def stop_monitoring(self):
        """停止性能监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("数据库性能监控已停止")

    def _monitoring_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                self._collect_metrics()
                self._check_alerts()
                time.sleep(PerformanceConfig.MONITORING_INTERVAL)
            except Exception as e:
                print(f"监控循环错误: {e}")
                time.sleep(5)

    def _collect_metrics(self):
        """收集性能指标"""
        # 收集连接池指标
        try:
            stats = get_connection_stats()
            self.metrics['connection_pool'] = stats
        except Exception as e:
            print(f"收集连接池指标失败: {e}")

        # 收集缓存指标
        try:
            self._collect_cache_metrics()
        except Exception as e:
            print(f"收集缓存指标失败: {e}")

    def _collect_cache_metrics(self):
        """收集缓存指标"""
        # 这里可以集成缓存监控
        self.metrics['cache_stats'] = {
            'hit_rate': 0.0,
            'miss_rate': 0.0,
            'total_requests': 0
        }

    def _check_alerts(self):
        """检查告警条件"""
        current_time = time.time()

        # 检查连接池告警
        self._check_connection_alerts(current_time)

        # 检查缓存告警
        self._check_cache_alerts(current_time)

    def _check_connection_alerts(self, current_time):
        """检查连接池告警"""
        pool_stats = self.metrics.get('connection_pool', {})
        active_connections = pool_stats.get('active_connections', 0)

        critical_threshold = PerformanceConfig.CONNECTION_CRITICAL_THRESHOLD
        if active_connections >= critical_threshold:
            self._trigger_alert(
                'connection_critical',
                f"连接池严重告警: {active_connections} 个活跃连接",
                current_time
            )
        warning_threshold = PerformanceConfig.CONNECTION_WARNING_THRESHOLD
        if active_connections >= warning_threshold:
            self._trigger_alert(
                'connection_warning',
                f"连接池警告: {active_connections} 个活跃连接",
                current_time
            )

    def _check_cache_alerts(self, current_time):
        """检查缓存告警"""
        cache_stats = self.metrics.get('cache_stats', {})
        hit_rate = cache_stats.get('hit_rate', 1.0)

        critical_rate = PerformanceConfig.CACHE_HIT_RATE_CRITICAL
        if hit_rate <= critical_rate:
            self._trigger_alert(
                'cache_critical',
                f"缓存命中率严重告警: {hit_rate:.2%}",
                current_time
            )
        warning_rate = PerformanceConfig.CACHE_HIT_RATE_WARNING
        if hit_rate <= warning_rate:
            self._trigger_alert(
                'cache_warning',
                f"缓存命中率警告: {hit_rate:.2%}",
                current_time
            )

    def _trigger_alert(self, alert_type: str, message: str,
                       current_time: float):
        """触发告警"""
        # 检查冷却时间
        last_time = self.last_alert_time.get(alert_type, 0)
        cooldown = PerformanceConfig.ALERT_COOLDOWN
        if current_time - last_time < cooldown:
            return

        alert = {
            'type': alert_type,
            'message': message,
            'timestamp': current_time,
            'datetime': datetime.fromtimestamp(current_time).isoformat()
        }

        self.metrics['alerts'].append(alert)
        self.last_alert_time[alert_type] = current_time

        print(f"🚨 告警: {message}")

    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        return {
            'monitoring_status': self.monitoring,
            'metrics': self.metrics,
            'recent_alerts': self.metrics['alerts'][-10:],  # 最近10个告警
            'timestamp': time.time()
        }

    def get_connection_pool_stats(self) -> Dict[str, Any]:
        """获取连接池统计"""
        return self.metrics.get('connection_pool', {})

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self.metrics.get('cache_stats', {})

    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的告警"""
        return self.metrics['alerts'][-limit:]

    def clear_alerts(self):
        """清空告警历史"""
        self.metrics['alerts'] = []
        self.last_alert_time = {}


# 全局监控器实例
_performance_monitor = None


def get_performance_monitor() -> DatabasePerformanceMonitor:
    """获取性能监控器实例"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = DatabasePerformanceMonitor()
    return _performance_monitor


def start_performance_monitoring():
    """启动性能监控"""
    get_performance_monitor().start_monitoring()


def stop_performance_monitoring():
    """停止性能监控"""
    get_performance_monitor().stop_monitoring()


def get_performance_report() -> Dict[str, Any]:
    """获取性能报告"""
    return get_performance_monitor().get_performance_report()


if __name__ == "__main__":
    # 测试监控功能
    performance_monitor = get_performance_monitor()
    performance_monitor.start_monitoring()

    try:
        print("性能监控测试运行中，按 Ctrl+C 停止...")
        while True:
            time.sleep(10)
            report = performance_monitor.get_performance_report()
            print(f"监控状态: {report['monitoring_status']}")
    except KeyboardInterrupt:
        print("\n停止监控...")
        performance_monitor.stop_monitoring()
