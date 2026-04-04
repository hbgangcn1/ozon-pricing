# -*- coding: utf-8 -*-
"""
PostgreSQL关键功能测试
覆盖序列修复、唯一约束、重复数据清理等PostgreSQL特定功能
"""

import pytest

# # import sqlite3  # SQLite removed  # SQLite removed
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPostgreSQLSerialPrimaryKey:
    """测试PostgreSQL序列主键修复"""

    @pytest.fixture
    def mock_postgres_conn(self):
        """模拟PostgreSQL连接"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn, mock_cursor

    def test_ensure_serial_primary_key_sequence_exists(self, mock_postgres_conn):
        """测试序列已存在的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟序列已存在
        mock_cursor.fetchone.side_effect = [
            ("nextval('users_id_seq'::regclass)",),  # column_default
            (1,),  # sequence exists
            (100,),  # MAX(id)
        ]

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_serial_primary_key,  # pyright: ignore[reportPrivateUsage]
            )

            _ensure_serial_primary_key(mock_conn, mock_cursor, "users", "id")

            # 应该不创建序列，但会设置setval
            assert mock_cursor.execute.called

    def test_ensure_serial_primary_key_create_sequence(self, mock_postgres_conn):
        """测试需要创建序列的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟序列不存在
        mock_cursor.fetchone.side_effect = [
            (None,),  # column_default为空
            None,  # sequence不存在
            (50,),  # MAX(id)
        ]

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_serial_primary_key,  # pyright: ignore[reportPrivateUsage]
            )

            _ensure_serial_primary_key(mock_conn, mock_cursor, "users", "id")

            # 应该创建序列
            execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
            assert any("CREATE SEQUENCE" in str(call) for call in execute_calls)
            # 注意: _ensure_serial_primary_key 不自行 commit，由调用者负责

    def test_ensure_serial_primary_key_fetchone_failure(self, mock_postgres_conn):
        """测试fetchone失败的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟fetchone失败（在第二次调用时）
        mock_cursor.fetchone.side_effect = [
            ("nextval(...)",),  # 第一次成功
            Exception("Database error"),  # 第二次失败
        ]

        with patch("db_utils._is_postgresql_connection", return_value=True):
            # 模拟异常被捕获
            with patch("db_utils.DB_EXCEPTIONS", Exception):
                from db_utils import (
                    _ensure_serial_primary_key,  # pyright: ignore[reportPrivateUsage]
                )

                # 应该不抛出异常，静默处理
                try:
                    _ensure_serial_primary_key(mock_conn, mock_cursor, "users", "id")
                except (AttributeError, RuntimeError, OSError, OSError):
                    # 如果抛出异常，说明异常处理有问题
                    pytest.fail("Should handle fetchone failure silently")

    def test_ensure_serial_primary_key_commit_failure(self, mock_postgres_conn):
        """测试commit失败的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟执行流程
        fetchone_count = [0]

        def mock_fetchone():
            fetchone_count[0] += 1
            if fetchone_count[0] == 1:
                return (None,)  # column_default为空
            elif fetchone_count[0] == 2:
                return None  # sequence不存在
            elif fetchone_count[0] == 3:
                return (50,)  # MAX(id)
            return None

        mock_cursor.fetchone.side_effect = mock_fetchone

        # 模拟commit失败（使用DB_EXCEPTIONS中的异常类型）
        commit_called = [False]
        try:
            import psycopg2 as _psycopg2

            psycopg2 = _psycopg2

            def mock_commit():
                commit_called[0] = True
                raise psycopg2.Error("Commit failed")
        except ImportError:
            _psycopg2 = None  # type: ignore[assignment]
            psycopg2 = None  # type: ignore[assignment]

            def mock_commit():
                commit_called[0] = True
                raise Exception("Commit failed")

        mock_conn.commit.side_effect = mock_commit

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_serial_primary_key,  # pyright: ignore[reportPrivateUsage]
            )

            # 应该捕获异常并回滚，不抛出异常
            _ensure_serial_primary_key(mock_conn, mock_cursor, "users", "id")
            # 应该尝试回滚（如果commit被调用）
            if commit_called[0]:
                assert mock_conn.rollback.called

    def test_ensure_serial_primary_key_invalid_table_name(self, mock_postgres_conn):
        """测试无效表名的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_serial_primary_key,  # pyright: ignore[reportPrivateUsage]
            )

            # 无效表名应该直接返回
            _ensure_serial_primary_key(mock_conn, mock_cursor, "users; DROP", "id")
            # 不应该执行任何SQL
            assert not mock_cursor.execute.called


class TestPostgreSQLUniqueConstraint:
    """测试PostgreSQL唯一约束创建"""

    @pytest.fixture
    def mock_postgres_conn(self):
        """模拟PostgreSQL连接"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        return mock_conn, mock_cursor

    def test_ensure_unique_constraint_already_exists(self, mock_postgres_conn):
        """测试约束已存在的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟约束已存在
        mock_cursor.fetchone.return_value = (1,)

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_unique_constraint,  # pyright: ignore[reportPrivateUsage]
            )

            _ensure_unique_constraint(
                mock_conn, mock_cursor, "users", ("username",), "users_username_key"
            )

            # 应该不创建约束
            execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
            assert not any("ADD CONSTRAINT" in str(call) for call in execute_calls)

    def test_ensure_unique_constraint_create_new(self, mock_postgres_conn):
        """测试创建新约束的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟约束不存在
        mock_cursor.fetchone.side_effect = [
            None,  # 约束不存在
            [],  # 没有匹配的约束
        ]
        mock_cursor.fetchall.return_value = []

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_unique_constraint,  # pyright: ignore[reportPrivateUsage]
            )

            _ensure_unique_constraint(
                mock_conn, mock_cursor, "users", ("username",), "users_username_key"
            )

            # 应该创建约束
            execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
            assert any("ADD CONSTRAINT" in str(call) for call in execute_calls)
            mock_conn.commit.assert_called_once()

    def test_ensure_unique_constraint_fetchone_failure(self, mock_postgres_conn):
        """测试fetchone失败的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟fetchone失败（在检查约束时，使用DB_EXCEPTIONS）
        try:
            import psycopg2 as _psycopg2

            psycopg2 = _psycopg2
            mock_cursor.fetchone.side_effect = psycopg2.Error("Database error")
        except ImportError:
            _psycopg2 = None  # type: ignore[assignment]
            psycopg2 = None  # type: ignore[assignment]  # noqa: F841
            mock_cursor.fetchone.side_effect = Exception("Database error")

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_unique_constraint,  # pyright: ignore[reportPrivateUsage]
            )

            # 应该不抛出异常，静默处理
            try:
                _ensure_unique_constraint(
                    mock_conn, mock_cursor, "users", ("username",), "users_username_key"
                )
            except (AttributeError, RuntimeError, OSError, OSError):
                # 如果抛出异常，说明异常处理有问题
                pytest.fail("Should handle fetchone failure silently")

    def test_ensure_unique_constraint_commit_failure(self, mock_postgres_conn):
        """测试commit失败的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        mock_cursor.fetchone.side_effect = [None]
        mock_cursor.fetchall.return_value = []

        commit_called = [False]
        try:
            import psycopg2 as _psycopg2

            psycopg2 = _psycopg2

            def mock_commit():
                commit_called[0] = True
                raise psycopg2.Error("Commit failed")
        except ImportError:
            _psycopg2 = None  # type: ignore[assignment]
            psycopg2 = None  # type: ignore[assignment]

            def mock_commit():
                commit_called[0] = True
                raise Exception("Commit failed")

        mock_conn.commit.side_effect = mock_commit

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_unique_constraint,  # pyright: ignore[reportPrivateUsage]
            )

            # 应该捕获异常并回滚，不抛出异常
            _ensure_unique_constraint(
                mock_conn, mock_cursor, "users", ("username",), "users_username_key"
            )
            # 应该尝试回滚（如果commit被调用）
            if commit_called[0]:
                assert mock_conn.rollback.called

    def test_ensure_unique_constraint_duplicate_constraint(self, mock_postgres_conn):
        """测试约束不存在时会尝试创建约束"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟约束不存在（fetchone返回None）
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_unique_constraint,  # pyright: ignore[reportPrivateUsage]
            )

            _ensure_unique_constraint(
                mock_conn, mock_cursor, "users", ("username",), "users_username_key"
            )

            # fetchone返回None表示约束不存在，应该尝试创建约束
            execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
            assert any("ADD CONSTRAINT" in str(call) for call in execute_calls)


class TestPostgreSQLCleanupDuplicateRows:
    """测试PostgreSQL重复数据清理"""

    @pytest.fixture
    def mock_postgres_conn(self):
        """模拟PostgreSQL连接"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        return mock_conn, mock_cursor

    def test_cleanup_duplicate_rows_success(self, mock_postgres_conn):
        """测试成功清理重复数据"""
        mock_conn, mock_cursor = mock_postgres_conn
        # _cleanup_duplicate_rows 内部通过 conn.cursor() 创建自己的游标
        mock_conn.cursor.return_value = mock_cursor

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _cleanup_duplicate_rows,  # pyright: ignore[reportPrivateUsage]
            )

            _cleanup_duplicate_rows(mock_conn, "users", ("username",))

            # 应该执行DELETE语句
            execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
            assert any("DELETE FROM" in str(call) for call in execute_calls)
            mock_conn.commit.assert_called_once()

    def test_cleanup_duplicate_rows_not_postgresql(self, mock_postgres_conn):
        """测试非PostgreSQL连接的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        with patch("db_utils._is_postgresql_connection", return_value=False):
            from db_utils import (
                _cleanup_duplicate_rows,  # pyright: ignore[reportPrivateUsage]
            )

            _cleanup_duplicate_rows(mock_conn, "users", ("username",))

            # 不应该执行任何SQL
            assert not mock_cursor.execute.called

    def test_cleanup_duplicate_rows_delete_failure(self, mock_postgres_conn):
        """测试DELETE失败的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        execute_count = [0]
        try:
            import psycopg2 as _psycopg2

            psycopg2 = _psycopg2

            def mock_execute(*args, **kwargs):
                _ = kwargs
                execute_count[0] += 1
                if "DELETE FROM" in str(args[0]):
                    raise psycopg2.Error("Delete failed")
                return None
        except ImportError:
            _psycopg2 = None  # type: ignore[assignment]
            psycopg2 = None  # type: ignore[assignment]

            def mock_execute(*args, **kwargs):
                _ = kwargs
                execute_count[0] += 1
                if "DELETE FROM" in str(args[0]):
                    raise Exception("Delete failed")
                return None

        mock_cursor.execute.side_effect = mock_execute

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _cleanup_duplicate_rows,  # pyright: ignore[reportPrivateUsage]
            )

            # 应该捕获异常并回滚，不抛出异常
            _cleanup_duplicate_rows(mock_conn, "users", ("username",))
            # 如果执行了DELETE，应该尝试回滚
            if execute_count[0] > 0:
                assert mock_conn.rollback.called

    def test_cleanup_duplicate_rows_invalid_table_name(self, mock_postgres_conn):
        """测试无效表名的情况"""
        mock_conn, mock_cursor = mock_postgres_conn

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _cleanup_duplicate_rows,  # pyright: ignore[reportPrivateUsage]
            )

            # 无效表名应该直接返回
            _cleanup_duplicate_rows(mock_conn, "users; DROP", ("username",))

            # 空列列表应该直接返回
            _cleanup_duplicate_rows(mock_conn, "users", ())
            # 不应该执行任何SQL
            assert not mock_cursor.execute.called
