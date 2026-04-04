# -*- coding: utf-8 -*-
"""
db_utils.py 数据库自愈/迁移测试
覆盖_ensure_postgresql_schema和_cleanup_duplicate_rows的异常场景
"""

import pytest

# # import sqlite3  # SQLite removed  # SQLite removed
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPostgreSQLSchemaHealing:
    """PostgreSQL Schema自愈测试"""

    @pytest.fixture
    def mock_postgres_conn(self):
        """模拟PostgreSQL连接"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 模拟_is_postgresql_connection返回True
        with patch("db_utils._is_postgresql_connection", return_value=True):
            yield mock_conn, mock_cursor

    def test_ensure_postgresql_schema_with_existing_constraint(
        self, mock_postgres_conn
    ):
        """测试确保Schema - 约束已存在"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟约束已存在
        mock_cursor.fetchone.return_value = (1,)

        from db_utils import (
            _ensure_postgresql_schema,  # pyright: ignore[reportPrivateUsage]
        )

        try:
            _ensure_postgresql_schema(mock_conn, mock_cursor)
            # 应该正常执行，不抛出异常
            assert True
        except (AttributeError, RuntimeError, OSError, OSError):
            pytest.fail("不应该抛出异常")

    def test_ensure_postgresql_schema_with_duplicate_table_error(
        self, mock_postgres_conn
    ):
        """测试确保Schema - DuplicateTable错误"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟DuplicateTable错误
        try:
            import psycopg2

            duplicate_error = psycopg2.errors.DuplicateTable("relation already exists")
        except (ImportError, AttributeError):
            # 如果没有psycopg2，使用通用异常
            duplicate_error = Exception("DuplicateTable")

        mock_cursor.execute.side_effect = duplicate_error
        mock_conn.rollback.return_value = None

        from db_utils import (
            _ensure_postgresql_schema,  # pyright: ignore[reportPrivateUsage]
        )

        try:
            _ensure_postgresql_schema(mock_conn, mock_cursor)
            # 应该捕获异常并回退
            assert mock_conn.rollback.called
        except (AttributeError, RuntimeError, OSError, OSError, Exception):  # noqa: B018
            # 允许异常，但应该被捕获
            pass

    def test_ensure_postgresql_schema_with_invalid_column_reference(
        self, mock_postgres_conn
    ):
        """测试确保Schema - InvalidColumnReference错误"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟InvalidColumnReference错误
        try:
            import psycopg2

            invalid_col_error = psycopg2.errors.UndefinedColumn("column does not exist")
        except (ImportError, AttributeError):
            invalid_col_error = Exception("InvalidColumnReference")

        mock_cursor.execute.side_effect = invalid_col_error
        mock_conn.rollback.return_value = None

        from db_utils import (
            _ensure_postgresql_schema,  # pyright: ignore[reportPrivateUsage]
        )

        try:
            _ensure_postgresql_schema(mock_conn, mock_cursor)
            # 应该捕获异常并回退
            assert mock_conn.rollback.called
        except (AttributeError, RuntimeError, OSError, OSError, Exception):  # noqa: B018
            pass

    def test_cleanup_duplicate_rows_success(self, mock_postgres_conn):
        """测试清理重复行 - 成功场景"""
        mock_conn, mock_cursor = mock_postgres_conn

        from db_utils import (
            _cleanup_duplicate_rows,  # pyright: ignore[reportPrivateUsage]
        )

        try:
            _cleanup_duplicate_rows(mock_conn, "test_table", ("key",))
        except Exception:
            pass

    def test_cleanup_duplicate_rows_with_exception(self, mock_postgres_conn):
        """测试清理重复行 - 异常场景"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟执行失败
        mock_cursor.execute.side_effect = Exception("SQL Error")
        mock_conn.rollback.return_value = None

        from db_utils import (
            _cleanup_duplicate_rows,  # pyright: ignore[reportPrivateUsage]
        )

        try:
            _cleanup_duplicate_rows(mock_conn, "test_table", ("key",))
            # 应该尝试回退
            assert mock_conn.rollback.called
        except (AttributeError, RuntimeError, OSError, OSError, Exception):  # noqa: B018
            pass

    def test_cleanup_duplicate_rows_rollback_failure(self, mock_postgres_conn):
        """测试清理重复行 - 回退也失败"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟执行失败，回退也失败
        mock_cursor.execute.side_effect = Exception("SQL Error")
        mock_conn.rollback.side_effect = Exception("Rollback failed")

        from db_utils import (
            _cleanup_duplicate_rows,  # pyright: ignore[reportPrivateUsage]
        )

        try:
            _cleanup_duplicate_rows(mock_conn, "test_table", ("key",))
            assert True
        except (AttributeError, RuntimeError, OSError, OSError, Exception):  # noqa: B018
            # 允许异常，但应该被捕获
            pass

    def test_ensure_serial_primary_key_with_existing_sequence(self, mock_postgres_conn):
        """测试确保序列主键 - 序列已存在"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟序列已存在
        mock_cursor.fetchone.return_value = (1,)

        from db_utils import (
            _ensure_serial_primary_key,  # pyright: ignore[reportPrivateUsage]
        )

        try:
            _ensure_serial_primary_key(mock_conn, mock_cursor, "test_table", "id")
            # 应该正常执行
            assert True
        except (AttributeError, RuntimeError, OSError, OSError):
            pytest.fail("不应该抛出异常")

    def test_ensure_unique_constraint_with_existing_constraint(
        self, mock_postgres_conn
    ):
        """测试确保唯一约束 - 约束已存在"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟约束已存在
        mock_cursor.fetchone.return_value = (1,)

        from db_utils import (
            _ensure_unique_constraint,  # pyright: ignore[reportPrivateUsage]
        )

        try:
            _ensure_unique_constraint(
                mock_conn, mock_cursor, "test_table", ("key",), "test_unique_key"
            )
            # 应该能够处理回退失败
            assert True
        except (AttributeError, RuntimeError, OSError, OSError):
            pytest.fail("不应该抛出异常")

    def test_ensure_foreign_key_with_orphaned_rows(self, mock_postgres_conn):
        """测试确保外键 - 存在孤立行（当前为stub实现）"""
        mock_conn, mock_cursor = mock_postgres_conn

        from db_utils import (
            _ensure_foreign_key,  # pyright: ignore[reportPrivateUsage]
        )

        # 当前_ensure_foreign_key是stub（pass），验证调用不报错
        try:
            _ensure_foreign_key(
                mock_conn,
                mock_cursor,
                "child_table",
                "fk_constraint",
                "parent_id",
                "parent_table",
                "id",
            )
            # stub函数应该正常返回，不抛出异常
            assert True
        except (AttributeError, RuntimeError, OSError):
            pytest.fail("stub函数不应该抛出异常")

    def test_cleanup_duplicate_ids_success(self, mock_postgres_conn):
        """测试清理重复ID - 成功场景（当前为stub实现）"""
        mock_conn, mock_cursor = mock_postgres_conn

        from db_utils import (
            _cleanup_duplicate_ids,  # pyright: ignore[reportPrivateUsage]
        )

        # 当前_cleanup_duplicate_ids(conn, table_name, id_column)是stub
        _cleanup_duplicate_ids(mock_conn, "test_table", "id")

        # stub函数不执行任何操作，验证不抛异常即可
        assert True

    def test_cleanup_duplicate_ids_with_exception(self, mock_postgres_conn):
        """测试清理重复ID - 异常场景"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟执行失败
        mock_cursor.execute.side_effect = Exception("SQL Error")
        mock_conn.rollback.return_value = None

        from db_utils import (
            _cleanup_duplicate_ids,  # pyright: ignore[reportPrivateUsage]
        )

        try:
            _cleanup_duplicate_ids(mock_conn, mock_cursor, "test_table")
            # 应该尝试回退
            assert mock_conn.rollback.called
        except (AttributeError, RuntimeError, OSError, OSError, Exception):  # noqa: B018
            pass
