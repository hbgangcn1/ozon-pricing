# -*- coding: utf-8 -*-
"""
接口限流模块
使用令牌桶算法和滑动窗口算法实现请求限流
高优先级安全改进：添加滑动窗口限流和监控告警
"""

import time
import streamlit as st
from functools import wraps
from threading import Lock
from typing import Callable, Optional, Dict, Any, List, Tuple
from collections import deque
from datetime import datetime


class TokenBucket:
    """令牌桶算法实现"""

    def __init__(self, rate: float, capacity: float):
        """
        初始化令牌桶

        Args:
            rate: 令牌生成速率（每秒生成的令牌数，支持小数）
            capacity: 桶的容量（最多存储的令牌数，支持小数以实现精确控制）
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = Lock()

    def consume(self, tokens: int = 1) -> bool:
        """
        尝试消费令牌

        Args:
            tokens: 要消费的令牌数

        Returns:
            bool: 是否成功消费
        """
        with self.lock:
            now = time.time()
            # 计算应该生成的令牌数
            elapsed = now - self.last_update
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.rate
            )
            self.last_update = now

            # 尝试消费令牌
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


class RateLimiter:
    """请求限流器"""

    def __init__(self, rate: int, per: int, burst: Optional[int] = None):
        """
        初始化限流器

        Args:
            rate: 允许的请求次数
            per: 时间窗口（秒）
            burst: 突发流量容量（默认等于rate）
        """
        self.rate = rate
        self.per = per
        self.burst = burst or rate
        self.buckets: Dict[str, TokenBucket] = {}
        self.lock = Lock()

    def _get_bucket(self, key: str) -> TokenBucket:
        """获取或创建令牌桶"""
        with self.lock:
            if key not in self.buckets:
                tokens_per_second = self.rate / self.per
                self.buckets[key] = TokenBucket(
                    rate=tokens_per_second,
                    capacity=self.burst
                )
            return self.buckets[key]

    def is_allowed(self, key: str, tokens: int = 1) -> bool:
        """
        检查是否允许请求

        Args:
            key: 限流键（通常是用户ID或IP地址）
            tokens: 要消费的令牌数

        Returns:
            bool: 是否允许请求
        """
        bucket = self._get_bucket(key)
        return bucket.consume(tokens)

    def get_retry_after(self, key: str) -> float:
        """
        获取重试等待时间

        Args:
            key: 限流键

        Returns:
            float: 需要等待的秒数
        """
        bucket = self._get_bucket(key)
        if bucket.tokens >= 1:
            return 0.0
        # 计算需要等待多久才能获得1个令牌
        return (1 - bucket.tokens) / bucket.rate

    def cleanup_old_buckets(self, max_age: int = 3600):
        """清理长时间未使用的令牌桶"""
        with self.lock:
            now = time.time()
            keys_to_remove = [
                key for key, bucket in self.buckets.items()
                if (now - bucket.last_update) > max_age
            ]
            for key in keys_to_remove:
                del self.buckets[key]


# 全局限流器实例
_limiters: Dict[str, RateLimiter] = {}


def get_limiter(
    name: str,
    rate: int,
    per: int,
    burst: Optional[int] = None
) -> RateLimiter:
    """
    获取限流器实例（单例模式）

    Args:
        name: 限流器名称
        rate: 允许的请求次数
        per: 时间窗口（秒）
        burst: 突发流量容量

    Returns:
        RateLimiter: 限流器实例
    """
    if name not in _limiters:
        _limiters[name] = RateLimiter(rate, per, burst)
    return _limiters[name]


def rate_limit(
    limiter_name: str,
    rate: int,
    per: int = 60,
    burst: Optional[int] = None,
    key_func: Optional[Callable[[], str]] = None,
    error_message: Optional[str] = None,
    use_sliding_window: bool = False
):
    """
    限流装饰器（高优先级安全改进：支持滑动窗口）

    Args:
        limiter_name: 限流器名称
        rate: 允许的请求次数
        per: 时间窗口（秒）
        burst: 突发流量容量（仅用于令牌桶）
        key_func: 自定义限流键函数
        error_message: 自定义错误消息
        use_sliding_window: 是否使用滑动窗口算法（默认False，使用令牌桶）

    Example:
        @rate_limit("login", rate=5, per=60)
        def login(username, password):
            pass

        @rate_limit("pricing", rate=30, per=60, use_sliding_window=True)
        def calculate_pricing():
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 获取限流键
            if key_func:
                key = key_func()
            else:
                # 默认使用用户ID，如果未登录则使用IP地址
                user_id = st.session_state.get('user_id')
                if user_id:
                    key = str(user_id)
                else:
                    # 尝试获取IP地址
                    try:
                        from session_security import SessionSecurity
                        client_info = SessionSecurity.get_client_info()
                        key = f"ip_{client_info['ip_address']}"
                    except (ImportError, AttributeError, KeyError, TypeError):
                        # 获取IP地址失败，使用匿名键
                        key = 'anonymous'

            # 使用滑动窗口或令牌桶
            if use_sliding_window:
                # 获取滑动窗口限流器实例
                sw_limiter = get_sliding_window_limiter(
                    limiter_name, rate, per
                )
                is_allowed, retry_after = sw_limiter.is_allowed(key)

                if not is_allowed:
                    # 记录告警
                    record_rate_limit_alert(
                        limiter_name, key, retry_after
                    )

                    if error_message:
                        message = error_message
                    else:
                        message = (
                            f"⚠️ 操作过于频繁，请 "
                            f"{int(retry_after) + 1} 秒后重试"
                        )

                    st.error(message)
                    st.warning(
                        f"限流规则: 每 {per} 秒最多 {rate} 次请求"
                    )
                    return None
            else:
                # 使用令牌桶算法
                bucket_limiter = get_limiter(limiter_name, rate, per, burst)

                if not bucket_limiter.is_allowed(key):
                    retry_after = bucket_limiter.get_retry_after(key)

                    # 记录告警
                    record_rate_limit_alert(
                        limiter_name, key, retry_after
                    )

                    if error_message:
                        message = error_message
                    else:
                        message = (
                            f"⚠️ 操作过于频繁，请 "
                            f"{int(retry_after) + 1} 秒后重试"
                        )

                    st.error(message)
                    st.warning(
                        f"限流规则: 每 {per} 秒最多 {rate} 次请求"
                    )
                    return None

            # 执行原函数
            return func(*args, **kwargs)

        return wrapper
    return decorator


def cleanup_all_limiters():
    """清理所有限流器中的旧数据"""
    for bucket_limiter in _limiters.values():
        bucket_limiter.cleanup_old_buckets()


class SlidingWindowLimiter:
    """
    滑动窗口限流器（高优先级安全改进）
    使用滑动窗口算法实现更精确的限流控制
    """

    def __init__(self, rate: int, per: int):
        """
        初始化滑动窗口限流器

        Args:
            rate: 允许的请求次数
            per: 时间窗口（秒）
        """
        self.rate = rate
        self.per = per
        self.windows: Dict[str, deque] = {}
        self.lock = Lock()
        self.stats: Dict[str, Dict[str, Any]] = {}  # 限流统计

    def is_allowed(self, key: str) -> Tuple[bool, float]:
        """
        检查是否允许请求

        Args:
            key: 限流键

        Returns:
            (is_allowed, retry_after): 是否允许，重试等待时间（秒）
        """
        with self.lock:
            now = time.time()

            # 获取或创建窗口
            if key not in self.windows:
                self.windows[key] = deque()
                self.stats[key] = {
                    'total_requests': 0,
                    'blocked_requests': 0,
                    'last_request': now,
                    'last_blocked': None
                }

            window = self.windows[key]
            stats = self.stats[key]

            # 清理过期的时间戳（超出时间窗口）
            cutoff_time = now - self.per
            while window and window[0] < cutoff_time:
                window.popleft()

            # 检查是否超过限制
            if len(window) >= self.rate:
                # 超过限制，计算重试等待时间
                oldest_timestamp = window[0] if window else now
                retry_after = self.per - (now - oldest_timestamp)
                stats['blocked_requests'] += 1
                stats['last_blocked'] = now
                return False, max(0, retry_after)

            # 允许请求，记录时间戳
            window.append(now)
            stats['total_requests'] += 1
            stats['last_request'] = now
            return True, 0.0

    def get_stats(self, key: str) -> Dict[str, Any]:
        """获取限流统计信息"""
        with self.lock:
            if key not in self.stats:
                return {}
            stats = self.stats[key].copy()
            stats['current_window_size'] = len(
                self.windows.get(key, deque())
            )
            return stats

    def cleanup_old_windows(self, max_age: int = 3600):
        """清理长时间未使用的窗口"""
        with self.lock:
            now = time.time()
            keys_to_remove = []
            for key, stats in self.stats.items():
                if now - stats['last_request'] > max_age:
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self.windows[key]
                del self.stats[key]


# 全局限流器实例（滑动窗口）
_sliding_window_limiters: Dict[str, SlidingWindowLimiter] = {}


def get_sliding_window_limiter(
    name: str, rate: int, per: int
) -> SlidingWindowLimiter:
    """
    获取滑动窗口限流器实例（单例模式）

    Args:
        name: 限流器名称
        rate: 允许的请求次数
        per: 时间窗口（秒）

    Returns:
        SlidingWindowLimiter: 限流器实例
    """
    if name not in _sliding_window_limiters:
        _sliding_window_limiters[name] = SlidingWindowLimiter(rate, per)
    return _sliding_window_limiters[name]


# 限流监控和告警
_rate_limit_alerts: List[Dict[str, Any]] = []
_max_alerts = 100  # 最多保留100条告警记录


def record_rate_limit_alert(
    limiter_name: str, key: str, retry_after: float
):
    """
    记录限流告警（高优先级安全改进）

    Args:
        limiter_name: 限流器名称
        key: 限流键（用户ID或IP）
        retry_after: 重试等待时间
    """
    alert = {
        'timestamp': datetime.now().isoformat(),
        'limiter_name': limiter_name,
        'key': key,
        'retry_after': retry_after
    }
    _rate_limit_alerts.append(alert)

    # 限制告警记录数量
    if len(_rate_limit_alerts) > _max_alerts:
        _rate_limit_alerts.pop(0)

    # 记录到日志（如果可用）
    try:
        from logger_config import logger
        if logger:
            logger.warning(
                f"限流告警: {limiter_name} - 键: {key}, "
                f"重试等待: {retry_after:.1f}秒"
            )
    except ImportError:
        pass


def get_rate_limit_alerts(
    limiter_name: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    获取限流告警记录

    Args:
        limiter_name: 限流器名称（可选，过滤）
        limit: 返回记录数量限制

    Returns:
        List[Dict]: 告警记录列表
    """
    alerts = _rate_limit_alerts
    if limiter_name:
        alerts = [
            a for a in alerts
            if a['limiter_name'] == limiter_name
        ]
    return alerts[-limit:]


def get_rate_limit_stats() -> Dict[str, Any]:
    """
    获取所有限流器的统计信息

    Returns:
        Dict: 统计信息
    """
    stats = {
        'token_bucket_limiters': {},
        'sliding_window_limiters': {},
        'total_alerts': len(_rate_limit_alerts),
        'recent_alerts': get_rate_limit_alerts(limit=10)
    }

    # 令牌桶限流器统计
    for limiter_name, token_bucket in _limiters.items():
        stats['token_bucket_limiters'][limiter_name] = {
            'rate': token_bucket.rate,
            'per': token_bucket.per,
            'active_buckets': len(token_bucket.buckets)
        }

    # 滑动窗口限流器统计
    for limiter_name, window_limiter in _sliding_window_limiters.items():
        stats['sliding_window_limiters'][limiter_name] = {
            'rate': window_limiter.rate,
            'per': window_limiter.per,
            'active_windows': len(window_limiter.windows)
        }

    return stats


# Streamlit应用启动时定期清理
if 'rate_limiter_cleanup_time' not in st.session_state:
    st.session_state.rate_limiter_cleanup_time = time.time()

# 每小时清理一次
if time.time() - st.session_state.rate_limiter_cleanup_time > 3600:
    cleanup_all_limiters()
    # 清理滑动窗口限流器
    for sw_item in _sliding_window_limiters.values():
        sw_item.cleanup_old_windows()
    st.session_state.rate_limiter_cleanup_time = time.time()
