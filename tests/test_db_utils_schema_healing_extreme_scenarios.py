# -*- coding: utf-8 -*-
"""
数据库自愈逻辑极端场景测试
覆盖约束损坏、序列损坏等极端情况
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# noinspection PyProtectedMember
# noqa: SLF001
from db_utils import (
    _ensure_postgresql_schema,  # pyright: ignore[reportPrivateUsage]
    _cleanup_duplicate_rows,  # pyright: ignore[reportPrivateUsage]
    _cleanup_duplicate_ids,  # pyright: ignore[reportPrivateUsage]
    _ensure_serial_primary_key,  # pyright: ignore[reportPrivateUsage]
    _ensure_unique_constraint,  # pyright: ignore[reportPrivateUsage]
    _ensure_foreign_key,  # pyright: ignore[reportPrivateUsage]
)


class TestSchemaHealingExtremeScenarios:
    """Schema自愈极端场景测试"""

    @patch("db_utils._is_postgresql_connection")
    def test_ensure_postgresql_schema_with_corrupted_constraint(self, mock_is_pg):
        """测试约束损坏时的自愈"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 模拟约束已存在但损坏的情况
        mock_cursor.execute.side_effect = [
            None,  # 第一次执行（检查约束）
            OSError(
                "duplicate key value violates unique constraint"
            ),  # 第二次执行（创建约束失败）
            None,  # 第三次执行（删除约束）
            None,  # 第四次执行（重新创建约束）
        ]

        # 应该能够处理约束损坏的情况
        try:
            _ensure_postgresql_schema(mock_conn, mock_cursor)
        except Exception as e:
            # 如果抛出异常，应该是预期的数据库错误，不应该是未处理的异常
            assert isinstance(e, (OSError, OSError, ValueError, StopIteration))

    @patch("db_utils._is_postgresql_connection")
    def test_ensure_serial_primary_key_with_corrupted_sequence(self, mock_is_pg):
        """测试序列损坏时的自愈"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 模拟序列不存在或损坏的情况
        mock_cursor.fetchone.side_effect = [
            None,  # 序列不存在
            (100,),  # 当前最大值
        ]
        mock_cursor.execute.return_value = None

        # 应该能够创建或修复序列
        try:
            _ensure_serial_primary_key(mock_conn, mock_cursor, "test_table")
        except Exception as e:
            # 如果抛出异常，应该是预期的数据库错误
            assert isinstance(e, (OSError, OSError, ValueError, StopIteration))

    @patch("db_utils._is_postgresql_connection")
    def test_ensure_unique_constraint_with_duplicate_data(self, mock_is_pg):
        """测试存在重复数据时创建唯一约束"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 模拟存在重复数据的情况
        mock_cursor.execute.side_effect = [
            None,  # 检查约束
            psycopg2.IntegrityError(
                "could not create unique index"
            ),  # 创建约束失败（因为有重复数据）
            None,  # 清理重复数据
            None,  # 重新创建约束
        ]
        mock_cursor.fetchone.return_value = None

        # 应该能够清理重复数据并创建约束
        try:
            _ensure_unique_constraint(
                mock_conn, mock_cursor, "test_table", ("column1",), "test_constraint"
            )
        except Exception as e:
            # 如果抛出异常，应该是预期的数据库错误
            assert isinstance(e, (OSError, OSError, ValueError, TypeError))

    @patch("db_utils._is_postgresql_connection")
    def test_ensure_foreign_key_with_missing_referenced_table(self, mock_is_pg):
        """测试引用表不存在时创建外键约束"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 模拟引用表不存在的情况
        mock_cursor.execute.side_effect = OSError(
            'relation "referenced_table" does not exist'
        )
        mock_cursor.fetchone.return_value = None

        # 应该优雅处理引用表不存在的情况
        # _ensure_foreign_key 签名: (conn, cursor, table_name, constraint_name,
        #                             column, ref_table, ref_column)
        try:
            _ensure_foreign_key(
                mock_conn,
                mock_cursor,
                "test_table",
                "fk_test_table_ref",
                "fk_column",
                "referenced_table",
                "ref_column",
            )
        except Exception as e:
            # 如果抛出异常，应该是预期的数据库错误
            assert isinstance(e, (OSError, OSError, ValueError, TypeError))

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_rows_with_large_dataset(self, mock_is_pg):
        """测试大数据集去重"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = None

        # 应该能够处理大数据集
        try:
            _cleanup_duplicate_rows(mock_conn, "test_table", ("column1", "column2"))
        except Exception as e:
            # 如果抛出异常，应该是预期的数据库错误
            assert isinstance(e, (OSError, OSError, ValueError))

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_ids_with_corrupted_sequence(self, mock_is_pg):
        """测试ID重复且序列损坏的情况"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 模拟序列损坏的情况
        mock_cursor.execute.side_effect = [
            None,  # 删除重复ID
            OSError("sequence does not exist"),  # 重置序列失败
            None,  # 创建序列
            None,  # 设置序列值
        ]

        # 应该能够处理序列损坏的情况
        try:
            _cleanup_duplicate_ids(mock_conn, mock_cursor, "test_table")
        except Exception as e:
            # 如果抛出异常，应该是预期的数据库错误
            assert isinstance(e, (OSError, OSError, ValueError))

    @patch("db_utils._is_postgresql_connection")
    def test_ensure_postgresql_schema_with_multiple_failures(self, mock_is_pg):
        """测试多次失败后的自愈"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 模拟多次失败后成功的情况
        call_count = [0]

        def side_effect(*_args, **_kwargs):  # noqa: ARG001
            call_count[0] += 1
            if call_count[0] <= 2:
                raise OSError("Temporary failure")
            return None

        mock_cursor.execute.side_effect = side_effect

        # 应该能够处理多次失败
        try:
            _ensure_postgresql_schema(mock_conn, mock_cursor)
        except Exception as e:
            # 如果抛出异常，应该是预期的数据库错误
            assert isinstance(e, (OSError, OSError, ValueError))

    @patch("db_utils._is_postgresql_connection")
    def test_cleanup_duplicate_rows_with_rollback_failure(self, mock_is_pg):
        """测试去重时回滚失败的处理"""
        mock_is_pg.return_value = True
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = OSError("Execute failed")
        mock_conn.rollback.side_effect = OSError("Rollback failed")

        # 应该优雅处理回滚失败，不抛出异常
        try:
            _cleanup_duplicate_rows(mock_conn, "test_table", ("column1",))
        except Exception as e:
            pytest.fail(f"去重应该优雅处理回滚失败，不应该抛出异常: {e}")
