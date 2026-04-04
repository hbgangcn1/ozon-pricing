# -*- coding: utf-8 -*-
import threading
import time
import pytest

from session_security_helpers import DistributedLock, REDIS_AVAILABLE
from session_security import SessionSecurityEnhanced  # noqa: F401


class TestDistributedLock:
    def test_init_default_values(self):
        lock = DistributedLock("test_key")
        assert lock.key == "test_key"
        assert lock.timeout == 10
        assert lock.lock_acquired is False

    def test_init_custom_values(self):
        lock = DistributedLock("custom_key", timeout=30, redis_available=True)
        assert lock.key == "custom_key"
        assert lock.timeout == 30

    def test_acquire_local_lock_when_redis_not_available(self):
        lock = DistributedLock("test", redis_available=False)
        result = lock.acquire()
        assert result is True
        lock.release()

    def test_release_local_lock_when_redis_not_available(self):
        lock = DistributedLock("test", redis_available=False)
        lock.acquire()
        lock.release()
        assert lock.lock_acquired is False

    def test_acquire_and_release_local_lock(self):
        lock = DistributedLock("test_local", redis_available=False)
        result = lock.acquire()
        assert result is True
        assert lock.lock_acquired is True
        lock.release()
        assert lock.lock_acquired is False

    def test_acquire_context_manager(self):
        lock = DistributedLock("test_context", redis_available=False)

        with lock as acquired_lock:
            assert acquired_lock.lock_acquired is True

        assert lock.lock_acquired is False

    def test_concurrent_lock_acquisition(self):
        results = []
        lock_key = "concurrent_test"

        def worker(worker_id):
            lock = DistributedLock(lock_key, timeout=5, redis_available=False)
            try:
                with lock:
                    results.append(f"worker_{worker_id}_acquired")
                    time.sleep(0.01)
                    results.append(f"worker_{worker_id}_released")
            except Exception as e:
                results.append(f"worker_{worker_id}_error: {e}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        acquired_count = sum(1 for r in results if "acquired" in r)
        released_count = sum(1 for r in results if "released" in r)
        assert acquired_count == 3
        assert released_count == 3

    def test_lock_timeout_configuration(self):
        lock1 = DistributedLock("test1", timeout=5)
        lock2 = DistributedLock("test2", timeout=30)

        assert lock1.timeout == 5
        assert lock2.timeout == 30

    def test_lock_key_naming(self):
        lock = DistributedLock("user_123_session")
        assert lock.key == "user_123_session"

    def test_local_lock_exists(self):
        lock = DistributedLock("test")
        assert hasattr(lock, "local_lock")
        assert isinstance(lock.local_lock, type(threading.Lock()))


class TestDistributedLockEdgeCases:
    def test_empty_key(self):
        lock = DistributedLock("")
        assert lock.key == ""

    def test_special_characters_in_key(self):
        lock = DistributedLock("user:123:session/abc")
        assert lock.key == "user:123:session/abc"

    def test_zero_timeout(self):
        lock = DistributedLock("test", timeout=0)
        assert lock.timeout == 0

    def test_negative_timeout(self):
        lock = DistributedLock("test", timeout=-1)
        assert lock.timeout == -1


class TestRedisAvailability:
    def test_redis_available_flag(self):
        assert isinstance(REDIS_AVAILABLE, bool)

    def test_lock_respects_redis_availability(self):
        lock = DistributedLock("test", redis_available=True)
        expected = True and REDIS_AVAILABLE
        assert lock.redis_available == expected
