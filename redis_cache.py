# -*- coding: utf-8 -*-
"""
Redis缓存服务
提供高性能缓存层，减少数据库压力
"""

import json
import time
import hashlib
from typing import Any, Optional, Dict
from functools import wraps

# 尝试导入Redis
try:
    import redis
    from redis.exceptions import (
        RedisError,
        ConnectionError as RedisConnectionError,
    )
    _redis_available = True
except ImportError:
    _redis_available = False
    redis = None
    RedisError = Exception
    RedisConnectionError = Exception

REDIS_AVAILABLE = _redis_available

# 全局Redis连接
_redis_client: Optional[Any] = None
_redis_init_failed: bool = False  # 标记Redis是否初始化失败，避免反复超时重试
_redis_fail_time: float = 0.0    # 失败时间戳
_REDIS_RETRY_INTERVAL = 300      # 失败后 300 秒才重试

# 缓存配置
CACHE_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'password': None,
    'decode_responses': True,
    'socket_timeout': 1,
    'socket_connect_timeout': 1,
    'retry_on_timeout': False,
    'max_connections': 20,
}

# 默认TTL配置（秒）
DEFAULT_TTL = {
    'exchange_rate': 3600,  # 汇率缓存1小时
    'user_data': 1800,      # 用户数据缓存30分钟
    'product_data': 1800,   # 产品数据缓存30分钟
    'logistics_data': 1800,  # 物流数据缓存30分钟
    'statistics': 300,      # 统计数据缓存5分钟
    'session': 7200,        # 会话缓存2小时
    'default': 600,         # 默认缓存10分钟
}


def init_redis_client(config: Optional[Dict[str, Any]] = None) -> bool:
    """
    初始化Redis客户端

    Args:
        config: Redis配置字典

    Returns:
        bool: 是否初始化成功
    """
    global _redis_client, _redis_init_failed, _redis_fail_time

    if not REDIS_AVAILABLE:
        return False

    # 失败后短期内不重试
    if _redis_init_failed and (time.time() - _redis_fail_time) < _REDIS_RETRY_INTERVAL:
        return False

    try:
        final_config = {**CACHE_CONFIG}
        if config:
            final_config.update(config)

        if redis is None:
            return False
        pool = redis.ConnectionPool(**final_config)
        _redis_client = redis.Redis(connection_pool=pool)

        if _redis_client is not None:
            _redis_client.ping()
        _redis_init_failed = False
        return True

    except (RedisError, RedisConnectionError, OSError):
        _redis_client = None
        _redis_init_failed = True
        _redis_fail_time = time.time()
        return False


def get_redis_client() -> Optional[Any]:
    """获取Redis客户端，失败后短期内不重试"""
    if _redis_client is None:
        if _redis_init_failed and (time.time() - _redis_fail_time) < _REDIS_RETRY_INTERVAL:
            return None
        init_redis_client()
    return _redis_client


def cache_key(prefix: str, *args, **kwargs) -> str:
    """
    生成缓存键

    Args:
        prefix: 键前缀
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        str: 缓存键
    """
    # 将参数序列化为字符串
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])

    # 生成哈希值避免键过长
    key_string = f"{prefix}:{':'.join(key_parts)}"
    if len(key_string) > 250:  # Redis键长度限制
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{prefix}:hash:{key_hash}"

    return key_string


def get_cache(key: str) -> Optional[Any]:
    """
    获取缓存数据

    Args:
        key: 缓存键

    Returns:
        Any: 缓存数据，如果不存在返回None
    """
    client = get_redis_client()
    if not client:
        return None

    try:
        data = client.get(key)
        if data is None:
            return None

        # 尝试解析JSON
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            # 如果不是JSON，直接返回字符串
            return data

    except (RedisError, RedisConnectionError) as e:
        print(f"获取缓存失败: {e}")
        return None


def set_cache(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """
    设置缓存数据

    Args:
        key: 缓存键
        value: 缓存值
        ttl: 过期时间（秒），None表示使用默认TTL

    Returns:
        bool: 是否设置成功
    """
    client = get_redis_client()
    if not client:
        return False

    try:
        # 序列化数据
        if isinstance(value, (dict, list, tuple)):
            data = json.dumps(value, ensure_ascii=False)
        else:
            data = str(value)

        # 设置TTL
        if ttl is None:
            ttl = DEFAULT_TTL.get('default', 600)

        # 设置缓存
        result = client.setex(key, ttl, data)
        return bool(result)

    except (RedisError, RedisConnectionError, TypeError) as e:
        print(f"设置缓存失败: {e}")
        return False


def delete_cache(key: str) -> bool:
    """
    删除缓存

    Args:
        key: 缓存键

    Returns:
        bool: 是否删除成功
    """
    client = get_redis_client()
    if not client:
        return False

    try:
        result = client.delete(key)
        return bool(result)
    except (RedisError, RedisConnectionError) as e:
        print(f"删除缓存失败: {e}")
        return False


def delete_cache_pattern(pattern: str) -> int:
    """
    按模式删除缓存

    Args:
        pattern: 键模式（支持*通配符）

    Returns:
        int: 删除的键数量
    """
    client = get_redis_client()
    if not client:
        return 0

    try:
        keys = client.keys(pattern)
        if not keys:
            return 0

        result = client.delete(*keys)
        return result
    except (RedisError, RedisConnectionError) as e:
        print(f"按模式删除缓存失败: {e}")
        return 0


def clear_all_cache() -> bool:
    """清空所有缓存"""
    client = get_redis_client()
    if not client:
        return False

    try:
        client.flushdb()
        return True
    except (RedisError, RedisConnectionError) as e:
        print(f"清空缓存失败: {e}")
        return False


def get_cache_info() -> Dict[str, Any]:
    """获取缓存信息"""
    client = get_redis_client()
    if not client:
        return {'status': 'unavailable', 'error': 'Redis未连接'}

    try:
        info = client.info()
        return {
            'status': 'connected',
            'used_memory': info.get('used_memory_human', 'N/A'),
            'connected_clients': info.get('connected_clients', 0),
            'total_commands_processed': info.get(
                'total_commands_processed', 0
            ),
            'keyspace_hits': info.get('keyspace_hits', 0),
            'keyspace_misses': info.get('keyspace_misses', 0),
            'hit_rate': _calculate_hit_rate(info),
        }
    except (RedisError, RedisConnectionError) as e:
        return {'status': 'error', 'error': str(e)}


def _calculate_hit_rate(info: Dict[str, Any]) -> float:
    """计算缓存命中率"""
    hits = info.get('keyspace_hits', 0)
    misses = info.get('keyspace_misses', 0)
    total = hits + misses

    if total == 0:
        return 0.0

    return round(hits / total * 100, 2)


def cached(ttl: Optional[int] = None, key_prefix: str = 'default'):
    """
    缓存装饰器

    Args:
        ttl: 缓存时间（秒）
        key_prefix: 键前缀

    Usage:
        @cached(ttl=3600, key_prefix='user')
        def get_user_data(user_id: int):
            return expensive_operation(user_id)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            key = cache_key(key_prefix, func.__name__, *args, **kwargs)

            # 尝试从缓存获取
            cached_result = get_cache(key)
            if cached_result is not None:
                return cached_result

            # 执行函数
            result = func(*args, **kwargs)

            # 设置缓存
            set_cache(key, result, ttl)

            return result

        return wrapper
    return decorator


class CacheManager:
    """缓存管理器"""

    def __init__(self, prefix: str = 'logistics'):
        self.prefix = prefix

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        full_key = f"{self.prefix}:{key}"
        return get_cache(full_key)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存"""
        full_key = f"{self.prefix}:{key}"
        return set_cache(full_key, value, ttl)

    def delete(self, key: str) -> bool:
        """删除缓存"""
        full_key = f"{self.prefix}:{key}"
        return delete_cache(full_key)

    def clear_pattern(self, pattern: str) -> int:
        """按模式清除缓存"""
        full_pattern = f"{self.prefix}:{pattern}"
        return delete_cache_pattern(full_pattern)

    def clear_all(self) -> bool:
        """清除所有缓存"""
        return self.clear_pattern("*") > 0


# 全局缓存管理器实例
cache_manager = CacheManager()


def init_cache_system(config: Optional[Dict[str, Any]] = None) -> bool:
    """
    初始化缓存系统

    Args:
        config: Redis配置

    Returns:
        bool: 是否初始化成功
    """
    return init_redis_client(config)


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    return get_cache_info()


# 便捷函数


def cache_exchange_rate(rate: float, ttl: int = 3600) -> bool:
    """缓存汇率数据"""
    return cache_manager.set('exchange_rate', rate, ttl)


def get_cached_exchange_rate() -> Optional[float]:
    """获取缓存的汇率数据"""
    return cache_manager.get('exchange_rate')


def cache_user_data(
    user_id: int,
    data: Dict[str, Any],
    ttl: int = 1800,
) -> bool:
    """缓存用户数据"""
    key = f"user:{user_id}"
    return cache_manager.set(key, data, ttl)


def get_cached_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    """获取缓存的用户数据"""
    key = f"user:{user_id}"
    return cache_manager.get(key)


def cache_product_data(
    product_id: int,
    data: Dict[str, Any],
    ttl: int = 1800,
) -> bool:
    """缓存产品数据"""
    key = f"product:{product_id}"
    return cache_manager.set(key, data, ttl)


def get_cached_product_data(product_id: int) -> Optional[Dict[str, Any]]:
    """获取缓存的产品数据"""
    key = f"product:{product_id}"
    return cache_manager.get(key)


def cache_logistics_data(
    logistics_id: int,
    data: Dict[str, Any],
    ttl: int = 1800,
) -> bool:
    """缓存物流数据"""
    key = f"logistics:{logistics_id}"
    return cache_manager.set(key, data, ttl)


def get_cached_logistics_data(logistics_id: int) -> Optional[Dict[str, Any]]:
    """获取缓存的物流数据"""
    key = f"logistics:{logistics_id}"
    return cache_manager.get(key)


def invalidate_user_cache(user_id: int) -> bool:
    """使用户相关缓存失效"""
    patterns = [
        f"user:{user_id}",
        "product:*",  # 用户的产品数据
        "logistics:*",  # 用户的物流数据
    ]

    total_deleted = 0
    for pattern in patterns:
        deleted = cache_manager.clear_pattern(pattern)
        total_deleted += deleted

    return total_deleted > 0


if __name__ == "__main__":
    # 测试缓存系统
    print("测试Redis缓存系统...")

    # 初始化
    if init_cache_system():
        print("✓ Redis缓存系统初始化成功")

        # 测试基本功能
        test_key = "test:key"
        test_value = {"message": "Hello Redis!", "timestamp": time.time()}

        # 设置缓存
        if set_cache(test_key, test_value, 60):
            print("✓ 设置缓存成功")

        # 获取缓存
        cached_value = get_cache(test_key)
        if cached_value:
            print(f"✓ 获取缓存成功: {cached_value}")

        # 获取统计信息
        stats = get_cache_info()
        print(f"✓ 缓存统计: {stats}")

    else:
        print("❌ Redis缓存系统初始化失败")
