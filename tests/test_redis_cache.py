# -*- coding: utf-8 -*-
"""
Redis缓存服务测试
"""

import sys

import pytest
from unittest.mock import MagicMock, patch

# 导入被测试模块
import redis_cache
# noinspection PyProtectedMember
from redis_cache import (
    init_redis_client,
    get_redis_client,
    cache_key,
    get_cache,
    set_cache,
    delete_cache,
    delete_cache_pattern,
    clear_all_cache,
    get_cache_info,
    cached,
    CacheManager,
    cache_manager,  # pyright: ignore[reportUnusedImport]
    init_cache_system,
    get_cache_stats,
    cache_exchange_rate,
    get_cached_exchange_rate,
    cache_user_data,
    get_cached_user_data,
    cache_product_data,
    get_cached_product_data,
    cache_logistics_data,
    get_cached_logistics_data,
    invalidate_user_cache,
    REDIS_AVAILABLE,
    DEFAULT_TTL,
)


@pytest.fixture(autouse=True, scope="function")
def restore_redis_cache_module():
    """在每个测试前恢复 redis_cache 模块的原始函数
    
    这个 fixture 确保 test_redis_cache 测试使用真实的 redis_cache 模块，
    而不是被 conftest.py 全局 mock 的版本。
    
    注意：由于 conftest.py 可能在模块导入时就 mock 了 redis_cache，
    我们需要在测试文件中重新导入模块，确保使用原始版本。
    """
    # 重新导入模块以恢复原始函数
    # 这是最可靠的方法，确保模块是原始的
    import importlib
    
    # 重新导入 redis_cache 模块
    if 'redis_cache' in sys.modules:
        importlib.reload(sys.modules['redis_cache'])
    if 'logistics.redis_cache' in sys.modules:
        importlib.reload(sys.modules['logistics.redis_cache'])
    
    # 重新导入所有函数和常量，确保使用最新版本
    # 注意：由于 Python 的导入机制，我们需要重新导入到全局命名空间
    # 使用 globals() 字典来更新模块级别的变量，避免 global 声明导致的类型检查问题
    module_globals = globals()
    
    # 重新导入模块
    reloaded_module = importlib.reload(sys.modules.get('redis_cache', redis_cache))
    
    # 重新导入所有函数和常量
    from redis_cache import (  # noqa: F401
        init_redis_client,
        get_redis_client,
        cache_key,
        get_cache,
        set_cache,
        delete_cache,
        delete_cache_pattern,
        clear_all_cache,
        get_cache_info,
        cached,
        CacheManager,
        cache_manager,
        init_cache_system,
        get_cache_stats,
        cache_exchange_rate,
        get_cached_exchange_rate,
        cache_user_data,
        get_cached_user_data,
        cache_product_data,
        get_cached_product_data,
        cache_logistics_data,
        get_cached_logistics_data,
    invalidate_user_cache,
    REDIS_AVAILABLE,
    DEFAULT_TTL,
)
    
    # 更新模块全局命名空间，使用 globals() 字典避免 global 声明
    module_globals['redis_cache'] = reloaded_module
    module_globals['init_redis_client'] = init_redis_client
    module_globals['get_redis_client'] = get_redis_client
    module_globals['cache_key'] = cache_key
    module_globals['get_cache'] = get_cache
    module_globals['set_cache'] = set_cache
    module_globals['delete_cache'] = delete_cache
    module_globals['delete_cache_pattern'] = delete_cache_pattern
    module_globals['clear_all_cache'] = clear_all_cache
    module_globals['get_cache_info'] = get_cache_info
    module_globals['cached'] = cached
    module_globals['CacheManager'] = CacheManager
    module_globals['cache_manager'] = cache_manager
    module_globals['init_cache_system'] = init_cache_system
    module_globals['get_cache_stats'] = get_cache_stats
    module_globals['cache_exchange_rate'] = cache_exchange_rate
    module_globals['get_cached_exchange_rate'] = get_cached_exchange_rate
    module_globals['cache_user_data'] = cache_user_data
    module_globals['get_cached_user_data'] = get_cached_user_data
    module_globals['cache_product_data'] = cache_product_data
    module_globals['get_cached_product_data'] = get_cached_product_data
    module_globals['cache_logistics_data'] = cache_logistics_data
    module_globals['get_cached_logistics_data'] = get_cached_logistics_data
    module_globals['invalidate_user_cache'] = invalidate_user_cache
    module_globals['REDIS_AVAILABLE'] = REDIS_AVAILABLE
    # 使用 getattr 安全访问 protected 成员，避免直接导入
    module_globals['_redis_client'] = getattr(reloaded_module, '_redis_client', None)
    module_globals['DEFAULT_TTL'] = DEFAULT_TTL
    
    yield
    
    # 测试后不需要特殊清理，因为下一个测试会再次恢复


class TestCacheKey:
    """测试缓存键生成"""

    def test_cache_key_simple(self):
        """测试简单键生成"""
        key = cache_key("test", "value1", "value2")
        assert key == "test:value1:value2"

    def test_cache_key_with_kwargs(self):
        """测试带关键字参数的键生成"""
        key = cache_key("test", "arg1", param1="value1", param2="value2")
        assert "test:" in key
        assert "arg1" in key
        assert "param1=value1" in key
        assert "param2=value2" in key

    def test_cache_key_long_string(self):
        """测试长键自动哈希"""
        long_string = "x" * 300
        key = cache_key("test", long_string)
        assert key.startswith("test:hash:")
        assert len(key) < 300

    def test_cache_key_kwargs_sorted(self):
        """测试关键字参数排序"""
        key1 = cache_key("test", a=1, b=2)
        key2 = cache_key("test", b=2, a=1)
        assert key1 == key2


class TestInitRedisClient:
    """测试Redis客户端初始化"""

    @patch('redis_cache.REDIS_AVAILABLE', True)
    @patch('redis_cache.redis')
    def test_init_redis_client_success(self, mock_redis):
        """测试成功初始化Redis客户端"""
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.Redis.return_value = mock_client

        result = init_redis_client()
        assert result is True
        mock_redis.ConnectionPool.assert_called_once()
        mock_redis.Redis.assert_called_once()

    @patch('redis_cache.REDIS_AVAILABLE', True)
    @patch('redis_cache.redis')
    def test_init_redis_client_with_config(self, mock_redis):
        """测试使用自定义配置初始化"""
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.Redis.return_value = mock_client

        config = {'host': 'custom_host', 'port': 6380}
        result = init_redis_client(config)
        assert result is True

    @patch('redis_cache.REDIS_AVAILABLE', True)
    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="redis module not available")
    @patch('redis_cache.redis')
    def test_init_redis_client_connection_error(self, mock_redis):
        """测试连接错误处理"""
        from redis.exceptions import ConnectionError as RedisConnectionError
        mock_redis.ConnectionPool.side_effect = RedisConnectionError("连接失败")

        result = init_redis_client()
        assert result is False

    @patch('redis_cache.REDIS_AVAILABLE', False)
    def test_init_redis_client_not_available(self):
        """测试Redis不可用时"""
        result = init_redis_client()
        assert result is False


class TestGetRedisClient:
    """测试获取Redis客户端"""

    def test_get_redis_client_init_if_none(self):
        """测试客户端为None时自动初始化"""
        # 首先将_redis_client设置为None
        original_client = getattr(redis_cache, '_redis_client', None)
        setattr(redis_cache, '_redis_client', None)
        
        try:
            with patch('redis_cache.init_redis_client') as mock_init:
                mock_client = MagicMock()
                # 模拟init_redis_client会设置_redis_client
                def set_client():
                    setattr(redis_cache, '_redis_client', mock_client)
                    return True
                mock_init.side_effect = set_client
                
                client = get_redis_client()
                mock_init.assert_called_once()
                assert client == mock_client
        finally:
            setattr(redis_cache, '_redis_client', original_client)

    def test_get_redis_client_existing(self):
        """测试返回现有客户端"""
        mock_client = MagicMock()
        with patch('redis_cache._redis_client', mock_client):
            with patch('redis_cache.init_redis_client'):
                client = get_redis_client()
                assert client == mock_client


class TestGetCache:
    """测试获取缓存"""

    @patch('redis_cache.get_redis_client')
    def test_get_cache_success_json(self, mock_get_client):
        """测试成功获取JSON缓存"""
        mock_client = MagicMock()
        mock_client.get.return_value = '{"key": "value"}'
        mock_get_client.return_value = mock_client

        result = get_cache("test_key")
        assert result == {"key": "value"}
        mock_client.get.assert_called_once_with("test_key")

    @patch('redis_cache.get_redis_client')
    def test_get_cache_success_string(self, mock_get_client):
        """测试获取字符串缓存"""
        mock_client = MagicMock()
        mock_client.get.return_value = "simple_string"
        mock_get_client.return_value = mock_client

        result = get_cache("test_key")
        assert result == "simple_string"

    @patch('redis_cache.get_redis_client')
    def test_get_cache_not_found(self, mock_get_client):
        """测试缓存不存在"""
        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_get_client.return_value = mock_client

        result = get_cache("test_key")
        assert result is None

    @patch('redis_cache.get_redis_client')
    def test_get_cache_no_client(self, mock_get_client):
        """测试客户端不存在"""
        mock_get_client.return_value = None

        result = get_cache("test_key")
        assert result is None

    @patch('redis_cache.get_redis_client')
    def test_get_cache_invalid_json(self, mock_get_client):
        """测试无效JSON处理"""
        mock_client = MagicMock()
        mock_client.get.return_value = "invalid{json"
        mock_get_client.return_value = mock_client

        result = get_cache("test_key")
        assert result == "invalid{json"

    @patch('redis_cache.get_redis_client')
    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="redis module not available")
    def test_get_cache_redis_error(self, mock_get_client):
        """测试Redis错误处理"""
        from redis.exceptions import RedisError
        mock_client = MagicMock()
        mock_client.get.side_effect = RedisError("连接错误")
        mock_get_client.return_value = mock_client

        with patch('builtins.print'):
            result = get_cache("test_key")
            assert result is None


class TestSetCache:
    """测试设置缓存"""

    @patch('redis_cache.get_redis_client')
    def test_set_cache_dict(self, mock_get_client):
        """测试设置字典缓存"""
        mock_client = MagicMock()
        mock_client.setex.return_value = True
        mock_get_client.return_value = mock_client

        result = set_cache("test_key", {"key": "value"})
        assert result is True
        mock_client.setex.assert_called_once()

    @patch('redis_cache.get_redis_client')
    def test_set_cache_list(self, mock_get_client):
        """测试设置列表缓存"""
        mock_client = MagicMock()
        mock_client.setex.return_value = True
        mock_get_client.return_value = mock_client

        result = set_cache("test_key", [1, 2, 3])
        assert result is True

    @patch('redis_cache.get_redis_client')
    def test_set_cache_string(self, mock_get_client):
        """测试设置字符串缓存"""
        mock_client = MagicMock()
        mock_client.setex.return_value = True
        mock_get_client.return_value = mock_client

        result = set_cache("test_key", "simple_string")
        assert result is True

    @patch('redis_cache.get_redis_client')
    def test_set_cache_with_ttl(self, mock_get_client):
        """测试设置TTL"""
        mock_client = MagicMock()
        mock_client.setex.return_value = True
        mock_get_client.return_value = mock_client

        result = set_cache("test_key", "value", ttl=3600)
        assert result is True
        args = mock_client.setex.call_args[0]
        assert args[1] == 3600  # TTL

    @patch('redis_cache.get_redis_client')
    def test_set_cache_default_ttl(self, mock_get_client):
        """测试使用默认TTL"""
        mock_client = MagicMock()
        mock_client.setex.return_value = True
        mock_get_client.return_value = mock_client

        result = set_cache("test_key", "value")
        assert result is True
        args = mock_client.setex.call_args[0]
        assert args[1] == DEFAULT_TTL['default']

    @patch('redis_cache.get_redis_client')
    def test_set_cache_no_client(self, mock_get_client):
        """测试客户端不存在"""
        mock_get_client.return_value = None

        result = set_cache("test_key", "value")
        assert result is False

    @patch('redis_cache.get_redis_client')
    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="redis module not available")
    def test_set_cache_redis_error(self, mock_get_client):
        """测试Redis错误处理"""
        from redis.exceptions import RedisError
        mock_client = MagicMock()
        mock_client.setex.side_effect = RedisError("错误")
        mock_get_client.return_value = mock_client

        with patch('builtins.print'):
            result = set_cache("test_key", "value")
            assert result is False

    @patch('redis_cache.get_redis_client')
    def test_set_cache_type_error(self, mock_get_client):
        """测试类型错误处理"""
        mock_client = MagicMock()
        mock_client.setex.side_effect = TypeError("类型错误")
        mock_get_client.return_value = mock_client

        with patch('builtins.print'):
            result = set_cache("test_key", object())
            assert result is False


class TestDeleteCache:
    """测试删除缓存"""

    @patch('redis_cache.get_redis_client')
    def test_delete_cache_success(self, mock_get_client):
        """测试成功删除"""
        mock_client = MagicMock()
        mock_client.delete.return_value = 1
        mock_get_client.return_value = mock_client

        result = delete_cache("test_key")
        assert result is True
        mock_client.delete.assert_called_once_with("test_key")

    @patch('redis_cache.get_redis_client')
    def test_delete_cache_not_found(self, mock_get_client):
        """测试删除不存在的键"""
        mock_client = MagicMock()
        mock_client.delete.return_value = 0
        mock_get_client.return_value = mock_client

        result = delete_cache("test_key")
        assert result is False

    @patch('redis_cache.get_redis_client')
    def test_delete_cache_no_client(self, mock_get_client):
        """测试客户端不存在"""
        mock_get_client.return_value = None

        result = delete_cache("test_key")
        assert result is False

    @patch('redis_cache.get_redis_client')
    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="redis module not available")
    def test_delete_cache_redis_error(self, mock_get_client):
        """测试Redis错误处理"""
        from redis.exceptions import RedisError
        mock_client = MagicMock()
        mock_client.delete.side_effect = RedisError("错误")
        mock_get_client.return_value = mock_client

        with patch('builtins.print'):
            result = delete_cache("test_key")
            assert result is False


class TestDeleteCachePattern:
    """测试按模式删除缓存"""

    @patch('redis_cache.get_redis_client')
    def test_delete_cache_pattern_success(self, mock_get_client):
        """测试成功删除模式匹配的键"""
        mock_client = MagicMock()
        mock_client.keys.return_value = ["key1", "key2", "key3"]
        mock_client.delete.return_value = 3
        mock_get_client.return_value = mock_client

        result = delete_cache_pattern("test:*")
        assert result == 3
        mock_client.keys.assert_called_once_with("test:*")

    @patch('redis_cache.get_redis_client')
    def test_delete_cache_pattern_no_keys(self, mock_get_client):
        """测试没有匹配的键"""
        mock_client = MagicMock()
        mock_client.keys.return_value = []
        mock_get_client.return_value = mock_client

        result = delete_cache_pattern("test:*")
        assert result == 0

    @patch('redis_cache.get_redis_client')
    def test_delete_cache_pattern_no_client(self, mock_get_client):
        """测试客户端不存在"""
        mock_get_client.return_value = None

        result = delete_cache_pattern("test:*")
        assert result == 0

    @patch('redis_cache.get_redis_client')
    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="redis module not available")
    def test_delete_cache_pattern_redis_error(self, mock_get_client):
        """测试Redis错误处理"""
        from redis.exceptions import RedisError
        mock_client = MagicMock()
        mock_client.keys.side_effect = RedisError("错误")
        mock_get_client.return_value = mock_client

        with patch('builtins.print'):
            result = delete_cache_pattern("test:*")
            assert result == 0


class TestClearAllCache:
    """测试清空所有缓存"""

    @patch('redis_cache.get_redis_client')
    def test_clear_all_cache_success(self, mock_get_client):
        """测试成功清空"""
        mock_client = MagicMock()
        mock_client.flushdb.return_value = True
        mock_get_client.return_value = mock_client

        result = clear_all_cache()
        assert result is True
        mock_client.flushdb.assert_called_once()

    @patch('redis_cache.get_redis_client')
    def test_clear_all_cache_no_client(self, mock_get_client):
        """测试客户端不存在"""
        mock_get_client.return_value = None

        result = clear_all_cache()
        assert result is False

    @patch('redis_cache.get_redis_client')
    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="redis module not available")
    def test_clear_all_cache_redis_error(self, mock_get_client):
        """测试Redis错误处理"""
        from redis.exceptions import RedisError
        mock_client = MagicMock()
        mock_client.flushdb.side_effect = RedisError("错误")
        mock_get_client.return_value = mock_client

        with patch('builtins.print'):
            result = clear_all_cache()
            assert result is False


class TestGetCacheInfo:
    """测试获取缓存信息"""

    @patch('redis_cache.get_redis_client')
    def test_get_cache_info_success(self, mock_get_client):
        """测试成功获取信息"""
        mock_client = MagicMock()
        mock_client.info.return_value = {
            'used_memory_human': '1M',
            'connected_clients': 5,
            'total_commands_processed': 1000,
            'keyspace_hits': 800,
            'keyspace_misses': 200,
        }
        mock_get_client.return_value = mock_client

        result = get_cache_info()
        assert result['status'] == 'connected'
        assert result['used_memory'] == '1M'
        assert result['connected_clients'] == 5
        assert 'hit_rate' in result

    @patch('redis_cache.get_redis_client')
    def test_get_cache_info_no_client(self, mock_get_client):
        """测试客户端不存在"""
        mock_get_client.return_value = None

        result = get_cache_info()
        assert result['status'] == 'unavailable'

    @patch('redis_cache.get_redis_client')
    @pytest.mark.skipif(not REDIS_AVAILABLE, reason="redis module not available")
    def test_get_cache_info_redis_error(self, mock_get_client):
        """测试Redis错误处理"""
        from redis.exceptions import RedisError
        mock_client = MagicMock()
        mock_client.info.side_effect = RedisError("错误")
        mock_get_client.return_value = mock_client

        result = get_cache_info()
        assert result['status'] == 'error'
        assert 'error' in result


class TestCachedDecorator:
    """测试缓存装饰器"""

    @patch('redis_cache.get_cache')
    @patch('redis_cache.set_cache')
    @patch('redis_cache.cache_key')
    def test_cached_hit(self, mock_cache_key, mock_set_cache, mock_get_cache):
        """测试缓存命中"""
        mock_cache_key.return_value = "cache_key"
        mock_get_cache.return_value = "cached_value"

        @cached(ttl=3600, key_prefix='test')
        def test_func(_arg1, _arg2):  # noqa: ARG001
            return "original_value"

        result = test_func("a", "b")
        assert result == "cached_value"
        mock_get_cache.assert_called_once()
        mock_set_cache.assert_not_called()

    @patch('redis_cache.get_cache')
    @patch('redis_cache.set_cache')
    @patch('redis_cache.cache_key')
    def test_cached_miss(self, mock_cache_key, mock_set_cache, mock_get_cache):
        """测试缓存未命中"""
        mock_cache_key.return_value = "cache_key"
        mock_get_cache.return_value = None
        mock_set_cache.return_value = True

        @cached(ttl=3600, key_prefix='test')
        def test_func(_arg1, _arg2):  # noqa: ARG001
            return "original_value"

        result = test_func("a", "b")
        assert result == "original_value"
        mock_get_cache.assert_called_once()
        mock_set_cache.assert_called_once_with("cache_key", "original_value", 3600)


class TestCacheManager:
    """测试缓存管理器"""

    def test_cache_manager_init(self):
        """测试初始化"""
        manager = CacheManager(prefix="test")
        assert manager.prefix == "test"

    @patch('redis_cache.get_cache')
    def test_cache_manager_get(self, mock_get_cache):
        """测试获取缓存"""
        mock_get_cache.return_value = {"key": "value"}
        manager = CacheManager(prefix="test")

        result = manager.get("my_key")
        assert result == {"key": "value"}
        mock_get_cache.assert_called_once_with("test:my_key")

    @patch('redis_cache.set_cache')
    def test_cache_manager_set(self, mock_set_cache):
        """测试设置缓存"""
        mock_set_cache.return_value = True
        manager = CacheManager(prefix="test")

        result = manager.set("my_key", {"key": "value"}, ttl=3600)
        assert result is True
        mock_set_cache.assert_called_once_with("test:my_key", {"key": "value"}, 3600)

    @patch('redis_cache.delete_cache')
    def test_cache_manager_delete(self, mock_delete_cache):
        """测试删除缓存"""
        mock_delete_cache.return_value = True
        manager = CacheManager(prefix="test")

        result = manager.delete("my_key")
        assert result is True
        mock_delete_cache.assert_called_once_with("test:my_key")

    @patch('redis_cache.delete_cache_pattern')
    def test_cache_manager_clear_pattern(self, mock_delete_pattern):
        """测试按模式清除"""
        mock_delete_pattern.return_value = 5
        manager = CacheManager(prefix="test")

        result = manager.clear_pattern("user:*")
        assert result == 5
        mock_delete_pattern.assert_called_once_with("test:user:*")

    @patch('redis_cache.delete_cache_pattern')
    def test_cache_manager_clear_all(self, mock_delete_pattern):
        """测试清除所有"""
        mock_delete_pattern.return_value = 10
        manager = CacheManager(prefix="test")

        result = manager.clear_all()
        assert result is True
        mock_delete_pattern.assert_called_once_with("test:*")


class TestConvenienceFunctions:
    """测试便捷函数"""

    @patch('redis_cache.init_redis_client')
    def test_init_cache_system(self, mock_init):
        """测试初始化缓存系统"""
        mock_init.return_value = True
        result = init_cache_system()
        assert result is True

    @patch('redis_cache.get_cache_info')
    def test_get_cache_stats(self, mock_get_info):
        """测试获取缓存统计"""
        mock_get_info.return_value = {"status": "connected"}
        result = get_cache_stats()
        assert result == {"status": "connected"}

    @patch('redis_cache.cache_manager')
    def test_cache_exchange_rate(self, mock_manager):
        """测试缓存汇率"""
        mock_manager.set.return_value = True
        result = cache_exchange_rate(7.5, ttl=3600)
        assert result is True
        mock_manager.set.assert_called_once_with('exchange_rate', 7.5, 3600)

    @patch('redis_cache.cache_manager')
    def test_get_cached_exchange_rate(self, mock_manager):
        """测试获取缓存的汇率"""
        mock_manager.get.return_value = 7.5
        result = get_cached_exchange_rate()
        assert result == 7.5
        mock_manager.get.assert_called_once_with('exchange_rate')

    @patch('redis_cache.cache_manager')
    def test_cache_user_data(self, mock_manager):
        """测试缓存用户数据"""
        mock_manager.set.return_value = True
        data = {"name": "test", "id": 1}
        result = cache_user_data(1, data, ttl=1800)
        assert result is True
        mock_manager.set.assert_called_once_with('user:1', data, 1800)

    @patch('redis_cache.cache_manager')
    def test_get_cached_user_data(self, mock_manager):
        """测试获取缓存的用户数据"""
        mock_manager.get.return_value = {"name": "test"}
        result = get_cached_user_data(1)
        assert result == {"name": "test"}
        mock_manager.get.assert_called_once_with('user:1')

    @patch('redis_cache.cache_manager')
    def test_cache_product_data(self, mock_manager):
        """测试缓存产品数据"""
        mock_manager.set.return_value = True
        data = {"name": "product", "price": 100}
        result = cache_product_data(1, data)
        assert result is True
        mock_manager.set.assert_called_once_with('product:1', data, 1800)

    @patch('redis_cache.cache_manager')
    def test_get_cached_product_data(self, mock_manager):
        """测试获取缓存的产品数据"""
        mock_manager.get.return_value = {"name": "product"}
        result = get_cached_product_data(1)
        assert result == {"name": "product"}
        mock_manager.get.assert_called_once_with('product:1')

    @patch('redis_cache.cache_manager')
    def test_cache_logistics_data(self, mock_manager):
        """测试缓存物流数据"""
        mock_manager.set.return_value = True
        data = {"name": "logistics", "fee": 50}
        result = cache_logistics_data(1, data)
        assert result is True
        mock_manager.set.assert_called_once_with('logistics:1', data, 1800)

    @patch('redis_cache.cache_manager')
    def test_get_cached_logistics_data(self, mock_manager):
        """测试获取缓存的物流数据"""
        mock_manager.get.return_value = {"name": "logistics"}
        result = get_cached_logistics_data(1)
        assert result == {"name": "logistics"}
        mock_manager.get.assert_called_once_with('logistics:1')

    @patch('redis_cache.cache_manager')
    def test_invalidate_user_cache(self, mock_manager):
        """测试使用户缓存失效"""
        mock_manager.clear_pattern.side_effect = [5, 10, 3]
        result = invalidate_user_cache(1)
        assert result is True
        assert mock_manager.clear_pattern.call_count == 3
