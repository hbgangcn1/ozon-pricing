# -*- coding: utf-8 -*-
"""
智能缓存管理器
提供多层级缓存系统（L1内存缓存 + L2Redis缓存）
支持LRU淘汰策略和智能失效机制
"""

import threading
import time
from typing import Any, Dict, Optional, Callable
# from datetime import datetime  # 暂时未使用
from functools import wraps

try:
    from .redis_cache import CacheManager as RedisCache
    # 导入Redis异常类型用于异常处理
    try:
        from redis.exceptions import (
            RedisError,
            ConnectionError as RedisConnectionError,
        )
        REDIS_EXCEPTIONS = (RedisError, RedisConnectionError)
    except ImportError:
        # Redis未安装，使用通用异常类型
        RedisError = Exception  # type: ignore
        RedisConnectionError = Exception  # type: ignore
        REDIS_EXCEPTIONS = (Exception,)
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisCache = None  # type: ignore
    RedisError = Exception  # type: ignore
    RedisConnectionError = Exception  # type: ignore
    REDIS_EXCEPTIONS = (Exception,)
    # Redis未安装，自动使用内存缓存（静默处理）


class CacheConfig:
    """缓存配置类"""

    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl


class L1Cache:
    """L1内存缓存"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = {}
        self.access_times = {}
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self.lock:
            if key in self.cache:
                self.access_times[key] = time.time()
                return self.cache[key]
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """设置缓存值"""
        # noqa: ARG002 - ttl参数保留用于接口一致性，L1缓存使用LRU策略而非TTL
        _ = ttl  # 明确使用ttl参数以消除警告
        with self.lock:
            # 如果缓存已满，删除最久未使用的项
            if len(self.cache) >= self.max_size and key not in self.cache:
                self._evict_lru()

            self.cache[key] = value
            self.access_times[key] = time.time()
            return True

    def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                del self.access_times[key]
                return True
            return False

    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()

    def _evict_lru(self):
        """删除最久未使用的项"""
        if not self.access_times:
            return

        lru_key = min(self.access_times.keys(),
                      key=lambda k: self.access_times[k])
        del self.cache[lru_key]
        del self.access_times[lru_key]

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hit_rate': 0.0,  # 需要外部计算
                'keys': list(self.cache.keys())
            }


class IntelligentCacheManager:
    """智能缓存管理器"""

    def __init__(self, max_l1_size: int = 1000, default_ttl: int = 300):
        self.l1_cache = L1Cache(max_l1_size)
        self.default_ttl = default_ttl
        self.l2_cache: Optional[RedisCache] = None  # type: ignore
        self.stats = {
            'l1_hits': 0,
            'l1_misses': 0,
            'l2_hits': 0,
            'l2_misses': 0,
            'sets': 0,
            'deletes': 0,
            'evictions': 0,
            'total_operations': 0
        }
        self.lock = threading.RLock()

        # 初始化L2缓存
        if REDIS_AVAILABLE:
            try:
                self.l2_cache = RedisCache()  # type: ignore
                # 测试Redis连接是否可用
                if self.l2_cache:
                    # 尝试一个简单的get操作来验证连接
                    try:
                        self.l2_cache.get('__test_connection__')
                    except REDIS_EXCEPTIONS:
                        # Redis连接不可用，降级到L1缓存
                        self.l2_cache = None
            except REDIS_EXCEPTIONS:
                # Redis初始化失败，自动降级到L1内存缓存
                self.l2_cache = None

    def get(self, key: str, category: str = 'default') -> Optional[Any]:
        """获取缓存值"""
        with self.lock:
            self.stats['total_operations'] += 1

            # 先尝试L1缓存
            l1_key = f"{category}:{key}"
            value = self.l1_cache.get(l1_key)
            if value is not None:
                self.stats['l1_hits'] += 1
                return value

            self.stats['l1_misses'] += 1

            # 尝试L2缓存
            if self.l2_cache:
                try:
                    value = self.l2_cache.get(key)
                    if value is not None:
                        self.stats['l2_hits'] += 1
                        # 回写到L1缓存
                        self.l1_cache.set(l1_key, value, self.default_ttl)
                        return value
                    self.stats['l2_misses'] += 1
                except REDIS_EXCEPTIONS:
                    # L2缓存失败，静默降级（已记录在统计中）
                    self.stats['l2_misses'] += 1

            return None

    def set(self, key: str, value: Any, category: str = 'default',
            ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        with self.lock:
            self.stats['total_operations'] += 1
            self.stats['sets'] += 1

            ttl = ttl or self.default_ttl
            l1_key = f"{category}:{key}"

            # 设置L1缓存
            success = self.l1_cache.set(l1_key, value, ttl)

            # 设置L2缓存
            if self.l2_cache:
                try:
                    self.l2_cache.set(key, value, ttl)
                except REDIS_EXCEPTIONS:
                    # L2缓存设置失败，静默降级（L1缓存已设置成功）
                    pass

            return success

    def delete(self, key: str, category: str = 'default') -> bool:
        """删除缓存项"""
        with self.lock:
            self.stats['total_operations'] += 1
            self.stats['deletes'] += 1

            l1_key = f"{category}:{key}"
            success = self.l1_cache.delete(l1_key)

            # 删除L2缓存
            if self.l2_cache:
                try:
                    self.l2_cache.delete(key)
                except REDIS_EXCEPTIONS:
                    # L2缓存删除失败，静默继续（L1缓存已删除）
                    pass

            return success

    def clear(self, category: Optional[str] = None):
        """清空缓存"""
        with self.lock:
            if category:
                # 清空特定类别的缓存
                keys_to_delete = []
                for key in self.l1_cache.cache.keys():
                    if key.startswith(f"{category}:"):
                        keys_to_delete.append(key)

                for key in keys_to_delete:
                    self.l1_cache.delete(key)

                if self.l2_cache:
                    try:
                        self.l2_cache.clear_all()
                    except REDIS_EXCEPTIONS:
                        # L2缓存清空失败，静默继续（L1缓存已清空）
                        pass
            else:
                # 清空所有缓存
                self.l1_cache.clear()
                if self.l2_cache:
                    try:
                        self.l2_cache.clear_all()
                    except REDIS_EXCEPTIONS:
                        # L2缓存清空失败，静默继续（L1缓存已清空）
                        pass

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            l1_stats = self.l1_cache.get_stats()
            total_ops = self.stats['total_operations']
            l1_hit_rate = (self.stats['l1_hits'] / total_ops * 100
                           if total_ops > 0 else 0)
            l2_hit_rate = (self.stats['l2_hits'] / total_ops * 100
                           if total_ops > 0 else 0)

            stats = {
                'l1_cache': {
                    'size': l1_stats['size'],
                    'max_size': l1_stats['max_size'],
                    'hit_rate': l1_hit_rate,
                    'hits': self.stats['l1_hits'],
                    'misses': self.stats['l1_misses']
                },
                'l2_cache': {
                    'status': 'available' if self.l2_cache else 'unavailable',
                    'hit_rate': l2_hit_rate,
                    'hits': self.stats['l2_hits'],
                    'misses': self.stats['l2_misses']
                },
                'total_operations': total_ops,
                'sets': self.stats['sets'],
                'deletes': self.stats['deletes'],
                'evictions': self.stats['evictions']
            }

            return stats

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取综合统计信息"""
        stats = self.get_stats()
        if self.l2_cache:
            try:
                stats['l2_cache'] = {'status': 'available'}
            except Exception as e:
                stats['l2_cache'] = {'error': str(e)}
        else:
            stats['l2_cache'] = {'status': 'unavailable'}
        return stats


# 全局缓存管理器实例
_cache_manager = IntelligentCacheManager()


def cache_result(category: str = 'default', ttl: Optional[int] = None):
    """缓存结果装饰器"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"

            # 尝试从缓存获取
            result = _cache_manager.get(cache_key, category)
            if result is not None:
                return result

            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            _cache_manager.set(cache_key, result, category, ttl)
            return result

        return wrapper
    return decorator


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    return _cache_manager.get_comprehensive_stats()


def clear_cache(category: Optional[str] = None):
    """清空缓存"""
    if category:
        _cache_manager.clear(category)
    else:
        _cache_manager.l1_cache.clear()
        if _cache_manager.l2_cache:
            _cache_manager.l2_cache.clear_all()


def clear_category(category: str):
    """清空特定类别的缓存"""
    _cache_manager.clear(category)


if __name__ == "__main__":
    # 测试缓存功能
    @cache_result('test', ttl=60)
    def expensive_function(x: int) -> int:
        print(f"计算 expensive_function({x})")
        time.sleep(1)  # 模拟耗时操作
        return x * x

    print("测试智能缓存管理器...")
    print(f"第一次调用: {expensive_function(5)}")
    print(f"第二次调用（应该从缓存获取）: {expensive_function(5)}")
    print(f"缓存统计: {get_cache_stats()}")
