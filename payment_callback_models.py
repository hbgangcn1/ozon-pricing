# -*- coding: utf-8 -*-
"""支付回调监控的数据类与告警日志器。

拆分自 payment_callback_enhanced.py，遵守 AGENTS.md 单文件 <500 行约束。
对外接口（PaymentRetryRecord / PaymentAlert / _alert_logger）保持不变；
payment_callback_enhanced 仍作为统一导入入口（re-export）。
"""

import logging
import logging.handlers
from dataclasses import dataclass
from typing import Any, Dict, Optional


# 告警日志使用 RotatingFileHandler 防止无限增长
_alert_logger = logging.getLogger("payment_alerts")
_alert_handler = logging.handlers.RotatingFileHandler(
    "payment_alerts.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_alert_handler.setFormatter(logging.Formatter("%(message)s"))
_alert_logger.addHandler(_alert_handler)
_alert_logger.setLevel(logging.INFO)
_alert_logger.propagate = False


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
