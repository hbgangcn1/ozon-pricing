# -*- coding: utf-8 -*-
"""
接口限流模块
使用令牌桶算法实现请求限流
"""

import time
import streamlit as st
from functools import wraps
from threading import Lock
from typing import Callable, Optional, Dict, Any


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
    error_message: Optional[str] = None
):
    """
    限流装饰器

    Args:
        limiter_name: 限流器名称
        rate: 允许的请求次数
        per: 时间窗口（秒）
        burst: 突发流量容量
        key_func: 自定义限流键函数
        error_message: 自定义错误消息

    Example:
        @rate_limit("login", rate=5, per=60)
        def login(username, password):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 获取限流器
            limiter = get_limiter(limiter_name, rate, per, burst)

            # 获取限流键
            if key_func:
                key = key_func()
            else:
                # 默认使用用户ID，如果未登录则使用固定键
                key = str(st.session_state.get('user_id', 'anonymous'))

            # 检查是否允许请求
            if not limiter.is_allowed(key):
                retry_after = limiter.get_retry_after(key)

                if error_message:
                    message = error_message
                else:
                    message = f"⚠️ 操作过于频繁，请 {int(retry_after) + 1} 秒后重试"

                st.error(message)
                st.warning(f"限流规则: 每 {per} 秒最多 {rate} 次请求")
                return None

            # 执行原函数
            return func(*args, **kwargs)

        return wrapper
    return decorator


def cleanup_all_limiters():
    """清理所有限流器中的旧数据"""
    for limiter in _limiters.values():
        limiter.cleanup_old_buckets()


# Streamlit应用启动时定期清理
if 'rate_limiter_cleanup_time' not in st.session_state:
    st.session_state.rate_limiter_cleanup_time = time.time()

# 每小时清理一次
if time.time() - st.session_state.rate_limiter_cleanup_time > 3600:
    cleanup_all_limiters()
    st.session_state.rate_limiter_cleanup_time = time.time()
