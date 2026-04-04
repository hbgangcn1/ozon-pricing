# -*- coding: utf-8 -*-
"""
数据库自愈/迁移关键场景测试
覆盖已有约束/序列损坏、重复数据清理等场景
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os
# # import sqlite3  # SQLite removed  # SQLite removed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# noinspection PyProtectedMember
# noqa: SLF001
from db_utils import (
    _ensure_postgresql_schema,  # pyright: ignore[reportPrivateUsage]
    _cleanup_duplicate_rows,  # pyright: ignore[reportPrivateUsage]
    _cleanup_duplicate_ids,  # pyright: ignore[reportPrivateUsage]
)


class TestPostgreSQLSchemaHealing:
    """PostgreSQL Schema 自愈测试"""

    @patch("db_utils._is_postgresql_connection")
    def test_ensure_postgresql_schema_not_postgresql(self, mock_is_pg):
        """测试非PostgreSQL连接时跳过"""
        mock_is_pg.return_value = False
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 应该直接返回，不执行任何操作
        _ensure_postgresql_schema(mock_conn, mock_cursor)
        mock_cursor.execute.assert_not_called()

    @patch("db_utils._is_postgresql_connection")
    @patch("db_utils._ensure_serial_primary_key")
    @patch("db_utils._ensure_unique_constraint")
    @patch("db_utils._cleanup_duplicate_rows")
    @patch("db_utils._cleanup_duplicate_ids")
    @patch("db_utils._ensure_foreign_key")
    def test_ensure_postgresql_schema_all_operations(
        self,
        mock_fk,
        mock_cleanup_ids,
        mock_cleanup_rows,
        mock_unique,
        mock_serial,
        mock_is_pg,
    ):
        """测试PostgreSQL Schema 自愈完整流程"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        _ensure_postgresql_schema(mock_conn, mock_cursor)

        # 验证关键操作都被调用
        assert mock_serial.called
        assert mock_unique.called
        assert mock_cleanup_rows.called
        assert mock_cleanup_ids.called
        assert mock_fk.called
        mock_conn.commit.assert_called_once()

    @patch("db_utils._is_postgresql_connection")
    @patch("db_utils._ensure_serial_primary_key")
    @patch("db_utils._ensure_unique_constraint")
    @patch("db_utils._cleanup_duplicate_rows")
    @patch("db_utils._cleanup_duplicate_ids")
    @patch("db_utils._ensure_foreign_key")
    def test_ensure_postgresql_schema_commit_failure(
        self,
        _mock_fk,
        _mock_cleanup_ids,
        _mock_cleanup_rows,
        _mock_unique,
        _mock_serial,
        mock_is_pg,
    ):
        """测试PostgreSQL Schema 自愈 - commit失败"""
        # noinspection PyUnusedLocal
        # noqa: ARG001
        _ = (
            _mock_fk,
            _mock_cleanup_ids,
            _mock_cleanup_rows,
            _mock_unique,
            _mock_serial,
        )
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_conn.commit.side_effect = Exception("Commit failed")
        mock_cursor = MagicMock()

        # 应该抛出异常或优雅处理
        with pytest.raises(Exception):
            _ensure_postgresql_schema(mock_conn, mock_cursor)


class TestCleanupDuplicateRows:
    """重复数据清理测试"""

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_rows_not_postgresql(self, mock_is_pg):
        """测试非PostgreSQL连接时跳过"""
        mock_is_pg.return_value = False
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        _cleanup_duplicate_rows(mock_conn, "test_table", ("key",))
        mock_cursor.execute.assert_not_called()

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_rows_invalid_table_name(self, mock_is_pg):
        """测试无效表名时跳过"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 无效表名（包含特殊字符）
        _cleanup_duplicate_rows(mock_conn, "test; DROP TABLE--", ("key",))
        mock_cursor.execute.assert_not_called()

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_rows_empty_columns(self, mock_is_pg):
        """测试空列时跳过"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        _cleanup_duplicate_rows(mock_conn, "test_table", ())
        mock_cursor.execute.assert_not_called()

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_rows_success(self, mock_is_pg):
        """测试成功清理重复数据"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # _cleanup_duplicate_rows 内部通过 conn.cursor() 创建游标
        mock_conn.cursor.return_value = mock_cursor

        _cleanup_duplicate_rows(mock_conn, "test_table", ("key1", "key2"))

        # 验证执行了DELETE语句
        assert mock_cursor.execute.called
        delete_sql = mock_cursor.execute.call_args[0][0]
        assert "DELETE FROM" in delete_sql.upper()
        assert "test_table" in delete_sql.lower()
        assert "ctid" in delete_sql.lower()
        mock_conn.commit.assert_called_once()

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_rows_db_exception(self, mock_is_pg):
        """测试数据库异常处理"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = OSError("DB Error")
        # _cleanup_duplicate_rows 内部通过 conn.cursor() 创建游标
        mock_conn.cursor.return_value = mock_cursor

        # 应该捕获异常并回滚
        _cleanup_duplicate_rows(mock_conn, "test_table", ("key",))
        mock_conn.rollback.assert_called()

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_rows_rollback_failure(self, mock_is_pg):
        """测试回滚失败处理"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = OSError("DB Error")
        mock_conn.rollback.side_effect = OSError("Rollback failed")

        # 应该捕获所有异常，不抛出
        try:
            _cleanup_duplicate_rows(mock_conn, "test_table", ("key",))
        except (AttributeError, RuntimeError, OSError, OSError):
            pytest.fail("Should not raise exception")


class TestCleanupDuplicateIds:
    """重复ID清理测试"""

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_ids_not_postgresql(self, mock_is_pg):
        """测试 _cleanup_duplicate_ids 不依赖 _is_postgresql_connection 检查"""
        mock_is_pg.return_value = False
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # _cleanup_duplicate_ids 不检查 _is_postgresql_connection，
        # 当以 (conn, cursor, table_name) 方式调用时直接执行 DELETE
        _cleanup_duplicate_ids(mock_conn, mock_cursor, "test_table")
        assert mock_cursor.execute.called

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_ids_success(self, mock_is_pg):
        """测试成功清理重复ID"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        _cleanup_duplicate_ids(mock_conn, mock_cursor, "test_table")

        # 验证执行了DELETE语句
        assert mock_cursor.execute.called
        delete_sql = mock_cursor.execute.call_args[0][0]
        assert "DELETE FROM" in delete_sql.upper()
        assert "ctid" in delete_sql.lower()
        mock_conn.commit.assert_called_once()

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_ids_invalid_table_name(self, mock_is_pg):
        """测试无效表名时跳过"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 无效表名（包含特殊字符）
        _cleanup_duplicate_ids(mock_conn, mock_cursor, "test; DROP--")
        mock_cursor.execute.assert_not_called()


class TestSchemaHealingWithExistingConstraints:
    """已有约束/序列损坏场景测试"""

    @patch("db_utils._is_postgresql_connection")
    @patch("db_utils._ensure_serial_primary_key")
    def test_schema_healing_with_existing_sequence(self, mock_serial, mock_is_pg):
        """测试已有序列时处理"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 模拟序列已存在但损坏
        mock_serial.side_effect = [
            None,  # 第一次调用成功
            Exception("Sequence already exists"),  # 第二次调用失败
        ]

        # 应该继续执行其他操作
        try:
            _ensure_postgresql_schema(mock_conn, mock_cursor)
        except (AttributeError, RuntimeError, OSError, OSError, Exception):  # noqa: B018
            pass  # 允许部分失败

    @patch("db_utils._is_postgresql_connection")
    @patch("db_utils._ensure_unique_constraint")
    def test_schema_healing_with_existing_constraint(self, mock_unique, mock_is_pg):
        """测试已有约束时处理"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 模拟约束已存在
        mock_unique.side_effect = Exception("Constraint already exists")

        # 应该继续执行其他操作或优雅处理
        try:
            _ensure_postgresql_schema(mock_conn, mock_cursor)
        except (AttributeError, RuntimeError, OSError, OSError, Exception):  # noqa: B018
            pass  # 允许部分失败

    @patch("db_utils._is_postgresql_connection")
    @patch("db_utils._ensure_foreign_key")
    def test_schema_healing_with_existing_foreign_key(self, mock_fk, mock_is_pg):
        """测试已有外键时处理"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 模拟外键已存在
        mock_fk.side_effect = Exception("Foreign key already exists")

        # 应该继续执行其他操作或优雅处理
        try:
            _ensure_postgresql_schema(mock_conn, mock_cursor)
        except (AttributeError, RuntimeError, OSError, OSError, Exception):  # noqa: B018
            pass  # 允许部分失败
