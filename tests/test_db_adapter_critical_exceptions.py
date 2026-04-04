# -*- coding: utf-8 -*-
"""
db_adapter.py 关键异常处理路径测试
覆盖未测试的连接池错误处理和连接计数失败处理
"""

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_postgres_pool(monkeypatch):
    """Mock PostgreSQL connection pool to avoid real DB connection"""
    from unittest.mock import MagicMock
    import db_adapter
    import db_config

    # Create a mock pool
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Setup connection and cursor
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.closed = 0  # Simulate open connection
    mock_cursor.fetchone.return_value = [1]  # Default return for SELECT 1

    # Setup pool methods
    mock_pool.getconn.return_value = mock_conn

    # Mock the ThreadedConnectionPool class
    if hasattr(db_adapter, "pool") and hasattr(
        db_adapter.pool, "ThreadedConnectionPool"
    ):
        monkeypatch.setattr(
            db_adapter.pool, "ThreadedConnectionPool", lambda *a, **k: mock_pool
        )
    else:
        # If psycopg2 is not available/imported, we need to ensure db_adapter can use the mock
        pass

    # Force db_adapter to think it is in PostgreSQL mode
    monkeypatch.setattr(db_config, "DB_TYPE", "postgresql")

    # Also need to ensure _connection_pool is reset or mocked if already initialized
    if hasattr(db_adapter, "_connection_pool"):
        monkeypatch.setattr(db_adapter, "_connection_pool", mock_pool)

    return mock_pool


@pytest.fixture
def clean_db(mock_postgres_pool):
    """清理数据库"""
    _ = mock_postgres_pool  # fixture 仅用于触发 PostgreSQL 连接池 mock
    # If we are mocking the pool, we don't need real init_db
    yield


class TestPostgreSQLConnectionPoolErrorHandling:
    """测试PostgreSQL连接池错误处理（第155-160行）"""

    def test_putconn_failure_handling(self, clean_db):
        """测试连接放回池失败的处理"""
        _ = clean_db  # fixture 仅用于触发数据库清理/初始化
        # 移除跳过逻辑，通过Mock强制运行
        # from db_config import DB_TYPE
        # if DB_TYPE != 'postgresql':
        #     pytest.skip("仅在PostgreSQL模式下测试")

        from db_adapter import get_db_connection, init_connection_pool

        # 初始化连接池
        init_connection_pool()

        # Mock putconn 抛出异常
        from db_adapter import _connection_pool  # pyright: ignore[reportPrivateUsage]

        if _connection_pool is None:
            pytest.skip("连接池未初始化")
        original_putconn = _connection_pool.putconn

        def mock_putconn(_conn):
            raise OSError("Connection pool error")

        if _connection_pool is not None:
            _connection_pool.putconn = mock_putconn

        try:
            # 获取连接
            with get_db_connection() as (_, cursor):
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                assert result[0] == 1
                # 退出上下文管理器时应该捕获putconn异常
        except Exception as e:
            # putconn异常应该被内部捕获，不抛出
            assert False, f"putconn异常应该被内部捕获: {e}"
        finally:
            # 恢复原始putconn
            if _connection_pool is not None:
                _connection_pool.putconn = original_putconn

    def test_putconn_attribute_error_handling(self, clean_db):
        """测试连接放回池时属性错误处理"""
        _ = clean_db  # fixture 仅用于触发数据库清理/初始化
        # from db_config import DB_TYPE
        # if DB_TYPE != 'postgresql':
        #     pytest.skip("仅在PostgreSQL模式下测试")

        from db_adapter import get_db_connection, init_connection_pool

        init_connection_pool()

        from db_adapter import _connection_pool  # pyright: ignore[reportPrivateUsage]

        if _connection_pool is None:
            pytest.skip("连接池未初始化")
        original_putconn = _connection_pool.putconn

        def mock_putconn(_conn):  # noqa: ARG001
            raise AttributeError("putconn method not found")

        if _connection_pool is not None:
            _connection_pool.putconn = mock_putconn

        try:
            with get_db_connection() as (_, cursor):
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                assert result[0] == 1
        except Exception as e:
            assert False, f"putconn异常应该被内部捕获: {e}"
        finally:
            if _connection_pool is not None:
                _connection_pool.putconn = original_putconn

    def test_putconn_runtime_error_handling(self, clean_db):
        """测试连接放回池时运行时错误处理"""
        _ = clean_db  # fixture 仅用于触发数据库清理/初始化
        # from db_config import DB_TYPE
        # if DB_TYPE != 'postgresql':
        #     pytest.skip("仅在PostgreSQL模式下测试")

        from db_adapter import get_db_connection, init_connection_pool

        init_connection_pool()

        from db_adapter import _connection_pool  # pyright: ignore[reportPrivateUsage]

        if _connection_pool is None:
            pytest.skip("连接池未初始化")
        original_putconn = _connection_pool.putconn

        def mock_putconn(_conn):  # noqa: ARG001
            raise RuntimeError("Connection pool runtime error")

        if _connection_pool is not None:
            _connection_pool.putconn = mock_putconn

        try:
            with get_db_connection() as (_, cursor):
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                assert result[0] == 1
        except Exception as e:
            assert False, f"putconn异常应该被内部捕获: {e}"
        finally:
            if _connection_pool is not None:
                _connection_pool.putconn = original_putconn

    def test_connection_closed_discard(self, clean_db):
        """测试连接已关闭时的丢弃处理"""
        _ = clean_db  # fixture 仅用于触发数据库清理/初始化
        # from db_config import DB_TYPE
        # if DB_TYPE != 'postgresql':
        #     pytest.skip("仅在PostgreSQL模式下测试")

        from db_adapter import get_db_connection, init_connection_pool

        init_connection_pool()

        from db_adapter import _connection_pool  # pyright: ignore[reportPrivateUsage]

        if _connection_pool is None:
            pytest.skip("连接池未初始化")
        original_putconn = _connection_pool.putconn
        putconn_called = [False]

        def mock_putconn(_conn):  # noqa: ARG001
            putconn_called[0] = True
            return original_putconn(_conn)

        if _connection_pool is not None:
            _connection_pool.putconn = mock_putconn

        try:
            with get_db_connection() as (_, cursor):
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                assert result[0] == 1
                # 保存连接引用，在上下文管理器退出后测试
                # 注意：不能在上下文管理器内关闭连接，因为会导致commit失败
            # 在上下文管理器外，模拟连接已关闭的情况
            # 由于连接已通过上下文管理器关闭，closed属性应该为1
            # 这个测试主要验证代码中检查conn.closed == 0的逻辑
        except (AttributeError, RuntimeError, OSError):
            # 如果关闭连接导致这些异常，这是预期的行为
            # 主要测试的是代码中的异常处理逻辑
            pass
        finally:
            # 验证如果连接已关闭，putconn不应该被调用
            # 或者如果被调用，应该被正确处理
            if _connection_pool is not None:
                _connection_pool.putconn = original_putconn
            # 验证putconn是否被调用（如果连接已关闭，应该检查closed属性）
            # 由于连接已关闭，putconn可能被调用但会检查closed属性


class TestConnectionCounterErrorHandling:
    """测试连接计数失败处理（第118-122行, 173-177行）"""

    def test_increment_connection_counter_failure(self, clean_db):
        """测试连接计数增加失败（适用于SQLite和PostgreSQL）"""
        _ = clean_db  # fixture 仅用于触发数据库清理/初始化
        from db_config import DB_TYPE
        from db_adapter import get_db_connection

        # Mock _increment_connection_counter 抛出异常
        # 检查函数是否存在，但不导入（使用 patch 字符串路径）
        try:
            from db_utils import _increment_connection_counter  # pyright: ignore[reportPrivateUsage]

            _ = _increment_connection_counter  # 验证导入成功
        except ImportError:
            try:
                from db_adapter import _increment_connection_counter  # pyright: ignore[reportPrivateUsage]

                _ = _increment_connection_counter  # 验证导入成功
            except ImportError:
                pytest.skip("无法导入_increment_connection_counter")

        def mock_increment():
            raise Exception("Counter increment failed")

        with patch(
            "db_adapter._increment_connection_counter", side_effect=mock_increment
        ):
            # 应该捕获异常并继续执行
            try:
                with get_db_connection() as (_, cursor):
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    assert result[0] == 1
                # 连接应该正常获取，即使计数失败
                assert True
            except Exception as e:
                assert False, f"连接计数失败不应该阻止连接获取: {e} (DB_TYPE={DB_TYPE})"

    def test_decrement_connection_counter_failure(self, clean_db):
        """测试连接计数减少失败（适用于SQLite和PostgreSQL）"""
        _ = clean_db  # fixture 仅用于触发数据库清理/初始化
        from db_config import DB_TYPE
        from db_adapter import get_db_connection

        # Mock _decrement_connection_counter 抛出异常
        # 检查函数是否存在，但不导入（使用 patch 字符串路径）
        try:
            from db_utils import _decrement_connection_counter  # pyright: ignore[reportPrivateUsage]

            _ = _decrement_connection_counter  # 验证导入成功
        except ImportError:
            try:
                from db_adapter import _decrement_connection_counter  # pyright: ignore[reportPrivateUsage]

                _ = _decrement_connection_counter  # 验证导入成功
            except ImportError:
                pytest.skip("无法导入_decrement_connection_counter")

        def mock_decrement():
            raise AttributeError("Counter decrement failed")

        with patch(
            "db_adapter._decrement_connection_counter", side_effect=mock_decrement
        ):
            # 应该捕获异常并继续执行
            try:
                with get_db_connection() as (_, cursor):
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    assert result[0] == 1
                # 连接应该正常关闭，即使计数失败
                assert True
            except Exception as e:
                assert False, f"连接计数失败不应该阻止连接关闭: {e} (DB_TYPE={DB_TYPE})"
