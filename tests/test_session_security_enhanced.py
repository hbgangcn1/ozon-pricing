# -*- coding: utf-8 -*-
"""
session_security_enhanced.py 分布式锁单元测试
覆盖 DistributedLock 和 SessionSecurityEnhanced 的关键路径
"""

import importlib.util
import os
import threading
import time

import pytest

from db_utils import init_db, get_db_connection

# 直接从文件加载真实模块，绕过 conftest 的 mock
_module_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'session_security_enhanced.py'
)
_spec = importlib.util.spec_from_file_location(
    'session_security_enhanced_real', _module_path
)
if _spec is None or _spec.loader is None:
    raise ImportError("无法加载 session_security_enhanced 模块")
_sse_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sse_module)

DistributedLock = _sse_module.DistributedLock
SessionSecurityEnhanced = _sse_module.SessionSecurityEnhanced
REDIS_AVAILABLE = _sse_module.REDIS_AVAILABLE


@pytest.fixture(scope="module")
def setup_db():
    """初始化测试数据库"""
    init_db()
    yield


class TestDistributedLock:
    """DistributedLock 类测试"""

    def test_init_default_values(self):
        """测试默认初始化参数"""
        lock = DistributedLock("test_key")
        assert lock.key == "test_key"
        assert lock.timeout == 10
        assert lock.lock_acquired is False

    def test_init_custom_values(self):
        """测试自定义初始化参数"""
        lock = DistributedLock("custom_key", timeout=30, redis_available=True)
        assert lock.key == "custom_key"
        assert lock.timeout == 30

    def test_acquire_redis_lock_when_not_available(self):
        """测试 Redis 不可用时的锁获取"""
        lock = DistributedLock("test", redis_available=False)
        result = lock._acquire_redis_lock()
        assert result is False

    def test_release_redis_lock_when_not_available(self):
        """测试 Redis 不可用时的锁释放"""
        lock = DistributedLock("test", redis_available=False)
        result = lock._release_redis_lock()
        assert result is False

    def test_acquire_db_lock_success(self, setup_db):
        """测试数据库锁获取成功"""
        result = DistributedLock._acquire_db_lock()
        assert result is True

    def test_release_db_lock_success(self, setup_db):
        """测试数据库锁释放成功"""
        with get_db_connection() as (conn, _):
            result = DistributedLock._release_db_lock(conn)
            assert result is True

    def test_acquire_context_manager_db_fallback(self, setup_db):
        """测试上下文管理器使用数据库锁回退"""
        lock = DistributedLock("test_context", redis_available=False)

        with lock.acquire() as acquired_lock:
            assert acquired_lock.lock_acquired is True

        assert lock.lock_acquired is False

    def test_concurrent_lock_acquisition(self, setup_db):
        """测试并发锁获取"""
        results = []
        lock_key = "concurrent_test"

        def worker(worker_id):
            lock = DistributedLock(lock_key, timeout=5, redis_available=False)
            try:
                with lock.acquire():
                    results.append(f"worker_{worker_id}_acquired")
                    time.sleep(0.01)  # 模拟工作
                    results.append(f"worker_{worker_id}_released")
            except Exception as e:
                results.append(f"worker_{worker_id}_error: {e}")

        threads = [
            threading.Thread(target=worker, args=(i,))
            for i in range(3)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有 worker 都成功获取和释放了锁
        acquired_count = sum(1 for r in results if 'acquired' in r)
        released_count = sum(1 for r in results if 'released' in r)
        assert acquired_count == 3
        assert released_count == 3

    def test_lock_timeout_configuration(self):
        """测试锁超时配置"""
        lock1 = DistributedLock("test1", timeout=5)
        lock2 = DistributedLock("test2", timeout=30)
        
        assert lock1.timeout == 5
        assert lock2.timeout == 30

    def test_lock_key_naming(self):
        """测试锁键名"""
        lock = DistributedLock("user_123_session")
        assert lock.key == "user_123_session"

    def test_local_lock_exists(self):
        """测试本地锁存在"""
        lock = DistributedLock("test")
        assert hasattr(lock, 'local_lock')
        assert isinstance(lock.local_lock, type(threading.Lock()))


class TestDistributedLockEdgeCases:
    """DistributedLock 边界情况测试"""

    def test_empty_key(self):
        """测试空键名"""
        lock = DistributedLock("")
        assert lock.key == ""

    def test_special_characters_in_key(self):
        """测试键名中的特殊字符"""
        lock = DistributedLock("user:123:session/abc")
        assert lock.key == "user:123:session/abc"

    def test_zero_timeout(self):
        """测试零超时"""
        lock = DistributedLock("test", timeout=0)
        assert lock.timeout == 0

    def test_negative_timeout(self):
        """测试负超时（应该接受但可能无意义）"""
        lock = DistributedLock("test", timeout=-1)
        assert lock.timeout == -1


class TestRedisAvailability:
    """Redis 可用性测试"""

    def test_redis_available_flag(self):
        """测试 REDIS_AVAILABLE 标志"""
        # REDIS_AVAILABLE 应该是布尔值
        assert isinstance(REDIS_AVAILABLE, bool)

    def test_lock_respects_redis_availability(self):
        """测试锁遵守 Redis 可用性设置"""
        lock = DistributedLock("test", redis_available=True)
        # 即使设置 redis_available=True，如果 REDIS_AVAILABLE 为 False，
        # 实际的 redis_available 应该是 False
        expected = True and REDIS_AVAILABLE
        assert lock.redis_available == expected
