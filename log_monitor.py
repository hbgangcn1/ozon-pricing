# -*- coding: utf-8 -*-
"""
日志监控和告警系统
监控应用日志，检测异常模式，发送告警通知
"""

import re
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict
import threading

try:
    from logger_config import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


class LogMonitor:
    """日志监控器"""

    def __init__(
        self,
        log_dir: str = "logs",
        check_interval: int = 300,  # 5分钟检查一次
        error_threshold: int = 10,  # 5分钟内超过10个错误触发告警
        warning_threshold: int = 50,  # 5分钟内超过50个警告触发告警
        alert_cooldown: int = 3600,  # 告警冷却时间（1小时）
    ):
        self.log_dir = Path(log_dir)
        self.check_interval = check_interval
        self.error_threshold = error_threshold
        self.warning_threshold = warning_threshold
        self.alert_cooldown = alert_cooldown

        # 告警历史记录（避免重复告警）
        self.alert_history: Dict[str, float] = {}
        self.alert_lock = threading.Lock()

        # 监控模式
        self.error_patterns = [
            (r'ERROR|CRITICAL|FATAL', 'error'),
            (r'数据库连接失败|Database connection failed', 'db_error'),
            (r'支付.*失败|Payment.*failed', 'payment_error'),
            (r'认证失败|Authentication failed', 'auth_error'),
            (r'内存不足|Out of memory', 'memory_error'),
            (r'磁盘空间不足|Disk space', 'disk_error'),
            (r'服务.*停止|Service.*stopped', 'service_error'),
        ]

        # 告警文件
        self.alert_log_file = self.log_dir / "alerts.log"
        self.stats_file = self.log_dir / "monitor_stats.json"

        # 监控状态
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

    def _get_latest_log_file(self) -> Optional[Path]:
        """获取最新的日志文件"""
        if not self.log_dir.exists():
            return None

        # 查找今天的日志文件
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"logistics_{today}.log"
        error_log_file = self.log_dir / f"logistics_error_{today}.log"

        # 优先使用错误日志文件
        if error_log_file.exists():
            return error_log_file
        if log_file.exists():
            return log_file
        return None

    @staticmethod
    def _parse_log_line(line: str) -> Optional[Dict]:
        """解析日志行"""
        if not line.strip():
            return None

        # 匹配 loguru 格式
        # 格式: YYYY-MM-DD HH:mm:ss | LEVEL | module:function:line | message
        pattern = (
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| '
            r'(\w+)\s+\| '
            r'([^|]+) \| '
            r'(.*)'
        )
        match = re.match(pattern, line)
        if match:
            timestamp_str, level, location, message = match.groups()
            try:
                timestamp = datetime.strptime(
                    timestamp_str, "%Y-%m-%d %H:%M:%S"
                )
                return {
                    'timestamp': timestamp,
                    'level': level.upper(),
                    'location': location.strip(),
                    'message': message.strip(),
                }
            except ValueError:
                pass
        return None

    def _analyze_logs(
        self, log_file: Path, since: datetime
    ) -> Dict[str, Any]:
        """分析日志文件，统计错误和警告"""
        stats = {
            'errors': 0,
            'warnings': 0,
            'info': 0,
            'error_types': defaultdict(int),
            'error_messages': [],
            'warning_messages': [],
        }

        if not log_file.exists():
            return stats

        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    log_entry = self._parse_log_line(line)
                    if not log_entry:
                        continue

                    # 只分析指定时间之后的日志
                    if log_entry['timestamp'] < since:
                        continue

                    level = log_entry['level']
                    message = log_entry['message']

                    # 统计各级别日志
                    if level in ['ERROR', 'CRITICAL', 'FATAL']:
                        stats['errors'] += 1
                        stats['error_messages'].append({
                            'time': log_entry['timestamp'].isoformat(),
                            'message': message[:200],  # 限制长度
                        })
                        # 匹配错误模式
                        for pattern, error_type in self.error_patterns:
                            if re.search(pattern, message, re.IGNORECASE):
                                stats['error_types'][error_type] += 1
                                break

                    elif level == 'WARNING':
                        stats['warnings'] += 1
                        if len(stats['warning_messages']) < 10:
                            stats['warning_messages'].append({
                                'time': log_entry['timestamp'].isoformat(),
                                'message': message[:200],
                            })

                    elif level == 'INFO':
                        stats['info'] += 1

        except Exception as e:
            logger.error(f"分析日志文件失败: {e}")

        return stats

    def _check_alert_cooldown(self, alert_key: str) -> bool:
        """检查告警是否在冷却期内"""
        with self.alert_lock:
            last_alert_time = self.alert_history.get(alert_key, 0)
            current_time = time.time()
            if current_time - last_alert_time < self.alert_cooldown:
                return True  # 在冷却期内
            return False

    def _record_alert(self, alert_key: str):
        """记录告警时间"""
        with self.alert_lock:
            self.alert_history[alert_key] = time.time()

    def _send_alert(
        self, alert_type: str, message: str, details: Dict
    ):
        """发送告警（记录到告警日志）"""
        alert_key = f"{alert_type}_{int(time.time() / self.alert_cooldown)}"

        # 检查冷却期
        if self._check_alert_cooldown(alert_key):
            logger.debug(f"告警 {alert_type} 在冷却期内，跳过")
            return

        # 记录告警
        alert_data = {
            'timestamp': datetime.now().isoformat(),
            'type': alert_type,
            'message': message,
            'details': details,
        }

        # 写入告警日志
        try:
            with open(self.alert_log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(alert_data, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"写入告警日志失败: {e}")

        # 记录告警时间
        self._record_alert(alert_key)

        # 输出告警信息
        logger.warning(f"🚨 告警: {message}")
        logger.warning(f"详情: {json.dumps(details, ensure_ascii=False)}")

    def check_logs(self) -> Dict[str, Any]:
        """检查日志并返回统计信息"""
        # 检查最近 check_interval 秒的日志
        since = datetime.now() - timedelta(seconds=self.check_interval)

        log_file = self._get_latest_log_file()
        if not log_file:
            logger.debug("未找到日志文件")
            return {
                'errors': 0,
                'warnings': 0,
                'alerts': [],
            }

        # 分析日志
        stats = self._analyze_logs(log_file, since)

        # 检查是否需要告警
        alerts = []

        # 错误数量告警
        if stats['errors'] >= self.error_threshold:
            alerts.append({
                'type': 'high_error_rate',
                'message': (
                    f"错误率过高: 在 {self.check_interval} 秒内检测到 "
                    f"{stats['errors']} 个错误（阈值: {self.error_threshold}）"
                ),
                'details': {
                    'error_count': stats['errors'],
                    'threshold': self.error_threshold,
                    'error_types': dict(stats['error_types']),
                    'sample_errors': stats['error_messages'][:5],
                },
            })

        # 警告数量告警
        if stats['warnings'] >= self.warning_threshold:
            alerts.append({
                'type': 'high_warning_rate',
                'message': (
                    f"警告率过高: 在 {self.check_interval} 秒内检测到 "
                    f"{stats['warnings']} 个警告（阈值: {self.warning_threshold}）"
                ),
                'details': {
                    'warning_count': stats['warnings'],
                    'threshold': self.warning_threshold,
                    'sample_warnings': stats['warning_messages'][:5],
                },
            })

        # 特定错误类型告警
        for error_type, count in stats['error_types'].items():
            if count >= 5:  # 同一类型错误超过5次
                alerts.append({
                    'type': f'{error_type}_pattern',
                    'message': (
                        f"检测到重复错误模式: {error_type} "
                        f"（{count} 次）"
                    ),
                    'details': {
                        'error_type': error_type,
                        'count': count,
                        'sample_errors': [
                            e for e in stats['error_messages']
                            if error_type in str(e)
                        ][:3],
                    },
                })

        # 发送告警
        for alert in alerts:
            self._send_alert(
                alert['type'],
                alert['message'],
                alert['details']
            )

        # 保存统计信息
        try:
            stats_data = {
                'timestamp': datetime.now().isoformat(),
                'stats': {
                    'errors': stats['errors'],
                    'warnings': stats['warnings'],
                    'info': stats['info'],
                    'error_types': dict(stats['error_types']),
                },
                'alerts_count': len(alerts),
            }
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存统计信息失败: {e}")

        return {
            'errors': stats['errors'],
            'warnings': stats['warnings'],
            'alerts': alerts,
            'stats': stats,
        }

    def start_monitoring(self):
        """启动监控线程"""
        if self.monitoring:
            logger.warning("监控已在运行")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="LogMonitor"
        )
        self.monitor_thread.start()
        logger.info("日志监控已启动")

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("日志监控已停止")

    def _monitor_loop(self):
        """监控循环"""
        logger.info("日志监控循环已启动")
        while self.monitoring:
            try:
                self.check_logs()
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
            time.sleep(self.check_interval)

    def get_stats(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"读取统计信息失败: {e}")
        return {}

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """获取最近的告警"""
        alerts = []
        try:
            if self.alert_log_file.exists():
                with open(self.alert_log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        try:
                            alert = json.loads(line.strip())
                            alerts.append(alert)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"读取告警日志失败: {e}")
        return alerts


# 全局监控实例
_monitor_instance: Optional[LogMonitor] = None
_monitor_lock = threading.Lock()


def get_log_monitor() -> LogMonitor:
    """获取日志监控器实例（单例）"""
    global _monitor_instance
    if _monitor_instance is None:
        with _monitor_lock:
            if _monitor_instance is None:
                _monitor_instance = LogMonitor()
    return _monitor_instance


if __name__ == "__main__":
    # 直接运行：执行一次检查
    monitor = get_log_monitor()
    result = monitor.check_logs()
    print(json.dumps(result, ensure_ascii=False, indent=2))
