#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库健康检查器
监控数据库连接状态、性能和资源使用情况
"""

import sqlite3
import time
import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta

# 尝试导入 psutil（可选依赖）
try:
    import psutil  # type: ignore  # noqa: F401
except ImportError:
    PSUTIL_AVAILABLE = False
else:
    PSUTIL_AVAILABLE = True

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HealthCheckResult:
    """健康检查结果"""

    def __init__(
        self,
        timestamp: datetime,
        connection_count: int,
        active_connections: int,
        pool_size: int,
        max_connections: int,
        memory_usage: float,
        response_time: float,
        error_count: int,
        status: str,
        recommendations: List[str]
    ):
        self.timestamp = timestamp
        self.connection_count = connection_count
        self.active_connections = active_connections
        self.pool_size = pool_size
        self.max_connections = max_connections
        self.memory_usage = memory_usage
        self.response_time = response_time
        self.error_count = error_count
        self.status = status
        self.recommendations = recommendations


class DatabaseHealthChecker:
    """数据库健康检查器"""

    def __init__(self, db_path: str = 'pricing_system.db'):
        self.db_path = db_path
        self.check_history: List[HealthCheckResult] = []
        self.max_history = 100

    def check_connection_health(self) -> HealthCheckResult:
        """检查数据库连接健康状态"""
        start_time = time.time()
        error_count = 0
        recommendations = []

        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            cursor = conn.cursor()

            # 检查数据库完整性
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()
            if integrity_result[0] != 'ok':
                error_count += 1
                recommendations.append(
                    "数据库完整性检查失败，建议执行VACUUM"
                )

            # 检查数据库大小
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            db_size_mb = (page_count * page_size) / 1024 / 1024

            if db_size_mb > 1000:  # 超过1GB
                recommendations.append(
                    "数据库文件过大，建议进行数据归档"
                )

            # 检查索引使用情况
            cursor.execute("PRAGMA index_list('users')")
            indexes = cursor.fetchall()
            if len(indexes) < 3:  # 假设至少需要3个索引
                recommendations.append(
                    "用户表索引不足，建议添加更多索引"
                )

            conn.close()

        except sqlite3.Error as e:
            error_count += 1
            logger.error(f"数据库连接测试失败: {e}")
            recommendations.append(
                "数据库连接失败，检查数据库文件状态"
            )
        except Exception as e:
            error_count += 1
            logger.error(f"健康检查异常: {e}")
            recommendations.append("健康检查异常，检查系统状态")

        response_time = (time.time() - start_time) * 1000  # 毫秒

        # 获取连接统计（模拟）
        connection_count = self._get_connection_count()
        active_connections = connection_count
        pool_size = 10  # 假设连接池大小
        max_connections = 50

        # 获取内存使用情况
        memory_usage = self._get_memory_usage()

        # 确定状态
        if error_count > 0:
            status = 'critical'
        elif response_time > 1000 or memory_usage > 80:
            status = 'warning'
        else:
            status = 'healthy'

        result = HealthCheckResult(
            timestamp=datetime.now(),
            connection_count=connection_count,
            active_connections=active_connections,
            pool_size=pool_size,
            max_connections=max_connections,
            memory_usage=memory_usage,
            response_time=response_time,
            error_count=error_count,
            status=status,
            recommendations=recommendations
        )

        # 添加到历史记录
        self.check_history.append(result)
        if len(self.check_history) > self.max_history:
            self.check_history.pop(0)

        return result

    @staticmethod
    def _get_connection_count() -> int:
        """获取连接数（模拟）"""
        try:
            # 这里应该从实际的连接池获取统计信息
            # 暂时返回模拟数据
            return 5
        except (ValueError, TypeError, AttributeError):
            return 0

    @staticmethod
    def _get_memory_usage() -> float:
        """获取内存使用率（模拟）"""
        try:
            import psutil  # type: ignore  # noqa: F811
            return psutil.virtual_memory().percent
        except ImportError:
            return 50.0  # 默认值

    def get_health_trend(self, hours: int = 24) -> Dict[str, Any]:
        """获取健康趋势"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_checks = [
            check for check in self.check_history
            if check.timestamp >= cutoff_time
        ]

        if not recent_checks:
            return {'error': '没有足够的历史数据'}

        # 计算趋势
        healthy_count = sum(
            1 for check in recent_checks if check.status == 'healthy'
        )
        warning_count = sum(
            1 for check in recent_checks if check.status == 'warning'
        )
        critical_count = sum(
            1 for check in recent_checks if check.status == 'critical'
        )

        avg_response_time = (
            sum(check.response_time for check in recent_checks)
            / len(recent_checks)
        )
        avg_memory_usage = (
            sum(check.memory_usage for check in recent_checks)
            / len(recent_checks)
        )

        return {
            'total_checks': len(recent_checks),
            'healthy_percentage': (
                healthy_count / len(recent_checks)
            ) * 100,
            'warning_percentage': (
                warning_count / len(recent_checks)
            ) * 100,
            'critical_percentage': (
                critical_count / len(recent_checks)
            ) * 100,
            'avg_response_time': avg_response_time,
            'avg_memory_usage': avg_memory_usage,
            'trend': (
                'improving' if healthy_count > critical_count else 'declining'
            )
        }

    def generate_health_report(self) -> Dict[str, Any]:
        """生成健康报告"""
        current_check = self.check_connection_health()
        trend = self.get_health_trend()

        return {
            'current_status': {
                'status': current_check.status,
                'timestamp': current_check.timestamp.isoformat(),
                'connection_count': current_check.connection_count,
                'active_connections': current_check.active_connections,
                'response_time': current_check.response_time,
                'memory_usage': current_check.memory_usage,
                'error_count': current_check.error_count
            },
            'trend': trend,
            'recommendations': current_check.recommendations,
            'check_count': len(self.check_history)
        }


def main():
    """主函数"""
    import sys

    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'pricing_system.db'

    print(f"数据库健康检查: {db_path}")

    checker = DatabaseHealthChecker(db_path)

    # 执行健康检查
    print("\n执行健康检查...")
    result = checker.check_connection_health()

    print("\n健康检查结果:")
    print(f"  状态: {result.status}")
    print(f"  连接数: {result.connection_count}")
    print(f"  活跃连接: {result.active_connections}")
    print(f"  响应时间: {result.response_time:.2f}ms")
    print(f"  内存使用: {result.memory_usage:.2f}%")
    print(f"  错误数: {result.error_count}")

    if result.recommendations:
        print("\n建议:")
        for rec in result.recommendations:
            print(f"  - {rec}")

    # 生成趋势报告
    trend = checker.get_health_trend()
    if 'error' not in trend:
        print("\n趋势分析 (过去24小时):")
        print(
            f"  健康率: {trend['healthy_percentage']:.2f}%"
        )
        print(
            f"  警告率: {trend['warning_percentage']:.2f}%"
        )
        print(
            f"  严重率: {trend['critical_percentage']:.2f}%"
        )
        print(
            f"  平均响应时间: {trend['avg_response_time']:.2f}ms"
        )


if __name__ == "__main__":
    main()
