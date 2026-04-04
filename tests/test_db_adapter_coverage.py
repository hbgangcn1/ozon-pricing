# -*- coding: utf-8 -*-
"""db_adapter.py 覆盖率补充测试 — 针对 52% → 90%+ 的未覆盖行"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


class TestAdaptSqlInsertOrReplace:
    """INSERT OR REPLACE → ON CONFLICT DO UPDATE 转换 (lines 272-298)"""

    def test_insert_or_replace_with_identifier_column(self):
        from db_adapter import adapt_sql

        sql = (
            "INSERT OR REPLACE INTO exchange_rates"
            " (identifier, rate, updated_at) VALUES (?, ?, ?)"
        )
        result = adapt_sql(sql)
        assert "INSERT INTO exchange_rates" in result
        assert "ON CONFLICT (identifier) DO UPDATE SET" in result
        assert "rate=EXCLUDED.rate" in result
        assert "updated_at=EXCLUDED.updated_at" in result
        assert "INSERT OR REPLACE" not in result

    def test_insert_or_replace_with_config_key_column(self):
        from db_adapter import adapt_sql

        sql = (
            "INSERT OR REPLACE INTO system_config"
            " (config_key, config_value) VALUES (?, ?)"
        )
        result = adapt_sql(sql)
        assert "ON CONFLICT (config_key) DO UPDATE SET" in result
        assert "config_value=EXCLUDED.config_value" in result

    def test_insert_or_replace_with_cache_key_column(self):
        from db_adapter import adapt_sql

        sql = (
            "INSERT OR REPLACE INTO cache_table"
            " (cache_key, data, expires) VALUES (?, ?, ?)"
        )
        result = adapt_sql(sql)
        assert "ON CONFLICT (cache_key) DO UPDATE SET" in result
        assert "data=EXCLUDED.data" in result

    def test_insert_or_replace_with_id_column(self):
        from db_adapter import adapt_sql

        sql = "INSERT OR REPLACE INTO users (id, name, email) VALUES (?, ?, ?)"
        result = adapt_sql(sql)
        assert "ON CONFLICT (id) DO UPDATE SET" in result
        assert "name=EXCLUDED.name" in result
        assert "email=EXCLUDED.email" in result

    def test_insert_or_replace_fallback_first_column(self):
        from db_adapter import adapt_sql

        sql = (
            "INSERT OR REPLACE INTO custom_table"
            " (custom_pk, val1, val2) VALUES (?, ?, ?)"
        )
        result = adapt_sql(sql)
        assert "ON CONFLICT (custom_pk) DO UPDATE SET" in result
        assert "val1=EXCLUDED.val1" in result
        assert "val2=EXCLUDED.val2" in result


class TestAdaptPlaceholdersMismatch:
    """adapt_placeholders 占位符数量不匹配 (line 351)"""

    def test_placeholder_count_mismatch_raises(self):
        from db_adapter import adapt_placeholders

        with pytest.raises(ValueError, match="占位符数量"):
            adapt_placeholders("SELECT ? FROM t WHERE id = ?", 3)

    def test_placeholder_count_zero_vs_nonzero(self):
        from db_adapter import adapt_placeholders

        with pytest.raises(ValueError, match="占位符数量"):
            adapt_placeholders("SELECT 1", 1)


class TestCloseConnectionPool:
    """close_connection_pool 正常关闭 (lines 111-115)"""

    def test_close_pool_calls_closeall(self):
        import db_adapter

        mock_pool = MagicMock()
        original = db_adapter._connection_pool
        try:
            db_adapter._connection_pool = mock_pool
            db_adapter.close_connection_pool()
            mock_pool.closeall.assert_called_once()
            assert db_adapter._connection_pool is None
        finally:
            db_adapter._connection_pool = original

    def test_close_pool_when_none_is_noop(self):
        import db_adapter

        original = db_adapter._connection_pool
        try:
            db_adapter._connection_pool = None
            db_adapter.close_connection_pool()
            assert db_adapter._connection_pool is None
        finally:
            db_adapter._connection_pool = original


class TestInitConnectionPoolErrors:
    """init_connection_pool 错误分支 (lines 79, 84)"""

    def test_psycopg2_not_available_raises(self):
        import db_adapter

        original_flag = db_adapter.PSYCOPG2_AVAILABLE
        original_pool = db_adapter._connection_pool
        try:
            db_adapter.PSYCOPG2_AVAILABLE = False
            db_adapter._connection_pool = None
            with pytest.raises(RuntimeError, match="PostgreSQL驱动未安装"):
                db_adapter.init_connection_pool()
        finally:
            db_adapter.PSYCOPG2_AVAILABLE = original_flag
            db_adapter._connection_pool = original_pool

    def test_pool_module_none_raises(self):
        import db_adapter

        original_pool_mod = db_adapter.pool
        original_conn_pool = db_adapter._connection_pool
        try:
            db_adapter.pool = None
            db_adapter._connection_pool = None
            with pytest.raises(RuntimeError, match="pool模块未正确加载"):
                db_adapter.init_connection_pool()
        finally:
            db_adapter.pool = original_pool_mod
            db_adapter._connection_pool = original_conn_pool


class TestGetDbConnectionErrors:
    """get_db_connection 早期错误检查 (lines 127, 132)"""

    def test_psycopg2_not_available_raises(self):
        import db_adapter

        original = db_adapter.PSYCOPG2_AVAILABLE
        try:
            db_adapter.PSYCOPG2_AVAILABLE = False
            with pytest.raises(RuntimeError, match="PostgreSQL驱动未安装"):
                with db_adapter.get_db_connection():
                    pass
        finally:
            db_adapter.PSYCOPG2_AVAILABLE = original

    def test_connection_pool_none_after_init_raises(self):
        import db_adapter

        original = db_adapter._connection_pool
        try:
            db_adapter._connection_pool = None
            with patch.object(
                db_adapter, "init_connection_pool", side_effect=lambda: None
            ):
                with pytest.raises(RuntimeError, match="连接池未正确初始化"):
                    with db_adapter.get_db_connection():
                        pass
        finally:
            db_adapter._connection_pool = original


class TestGetDbConnectionCommitErrors:
    """get_db_connection commit/rollback 错误路径 (lines 156-184)"""

    def _setup_pool_mock(self, db_adapter_mod):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.closed = 0
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn
        original = db_adapter_mod._connection_pool
        db_adapter_mod._connection_pool = mock_pool
        return original, mock_pool, mock_conn, mock_cursor

    def test_commit_oserror_suppressed_in_test_env(self):
        import db_adapter
        import os

        original, mock_pool, mock_conn, mock_cursor = self._setup_pool_mock(db_adapter)
        mock_conn.commit.side_effect = OSError("commit fail")
        try:
            os.environ["PYTEST_CURRENT_TEST"] = "yes"
            with db_adapter.get_db_connection() as (conn, cursor):
                pass
        finally:
            db_adapter._connection_pool = original

    def test_commit_attribute_error_suppressed(self):
        import db_adapter

        original, mock_pool, mock_conn, mock_cursor = self._setup_pool_mock(db_adapter)
        mock_conn.commit.side_effect = AttributeError("no commit")
        try:
            with db_adapter.get_db_connection() as (conn, cursor):
                pass
        finally:
            db_adapter._connection_pool = original

    def test_rollback_on_exception_with_open_conn(self):
        import db_adapter

        original, mock_pool, mock_conn, mock_cursor = self._setup_pool_mock(db_adapter)
        try:
            with pytest.raises(ValueError):
                with db_adapter.get_db_connection() as (conn, cursor):
                    raise ValueError("user error")
            mock_conn.rollback.assert_called_once()
        finally:
            db_adapter._connection_pool = original

    def test_rollback_oserror_suppressed(self):
        import db_adapter

        original, mock_pool, mock_conn, mock_cursor = self._setup_pool_mock(db_adapter)
        mock_conn.rollback.side_effect = OSError("rollback fail")
        try:
            with pytest.raises(ValueError):
                with db_adapter.get_db_connection() as (conn, cursor):
                    raise ValueError("user error")
        finally:
            db_adapter._connection_pool = original

    def test_exception_with_closed_conn_skips_rollback(self):
        import db_adapter

        original, mock_pool, mock_conn, mock_cursor = self._setup_pool_mock(db_adapter)
        mock_conn.closed = 1
        try:
            with pytest.raises(ValueError):
                with db_adapter.get_db_connection() as (conn, cursor):
                    raise ValueError("user error")
            mock_conn.rollback.assert_not_called()
        finally:
            db_adapter._connection_pool = original


class TestGetDbConnectionFinallyCleanup:
    """get_db_connection finally 块清理 (lines 189-227)"""

    def _setup_pool_mock(self, db_adapter_mod):
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.closed = 0
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn
        original = db_adapter_mod._connection_pool
        db_adapter_mod._connection_pool = mock_pool
        return original, mock_pool, mock_conn, mock_cursor

    def test_cursor_close_oserror_suppressed(self):
        import db_adapter

        original, mock_pool, mock_conn, mock_cursor = self._setup_pool_mock(db_adapter)
        mock_cursor.close.side_effect = OSError("cursor close fail")
        try:
            with db_adapter.get_db_connection() as (conn, cursor):
                pass
        finally:
            db_adapter._connection_pool = original

    def test_conn_closed_skips_putconn(self):
        import db_adapter

        original, mock_pool, mock_conn, mock_cursor = self._setup_pool_mock(db_adapter)
        mock_conn.closed = 0
        mock_conn.commit.side_effect = lambda: setattr(mock_conn, "closed", 1)
        try:
            with db_adapter.get_db_connection() as (conn, cursor):
                pass
            mock_pool.putconn.assert_not_called()
        finally:
            db_adapter._connection_pool = original

    def test_putconn_pool_error_closes_conn(self):
        import db_adapter

        original, mock_pool, mock_conn, mock_cursor = self._setup_pool_mock(db_adapter)
        mock_pool.putconn.side_effect = db_adapter.POOL_ERROR_TYPE("pool full")
        try:
            with db_adapter.get_db_connection() as (conn, cursor):
                pass
            mock_conn.close.assert_called()
        finally:
            db_adapter._connection_pool = original

    def test_putconn_pool_error_conn_close_fails(self):
        import db_adapter

        original, mock_pool, mock_conn, mock_cursor = self._setup_pool_mock(db_adapter)
        mock_pool.putconn.side_effect = db_adapter.POOL_ERROR_TYPE("pool full")
        mock_conn.close.side_effect = OSError("close fail")
        delattr_called = False
        try:
            with db_adapter.get_db_connection() as (conn, cursor):
                pass
        finally:
            db_adapter._connection_pool = original

    def test_putconn_type_error_closes_conn(self):
        import db_adapter

        original, mock_pool, mock_conn, mock_cursor = self._setup_pool_mock(db_adapter)
        mock_pool.putconn.side_effect = TypeError("bad type")
        try:
            with db_adapter.get_db_connection() as (conn, cursor):
                pass
            mock_conn.close.assert_called()
        finally:
            db_adapter._connection_pool = original

    def test_putconn_type_error_conn_close_also_fails(self):
        import db_adapter

        original, mock_pool, mock_conn, mock_cursor = self._setup_pool_mock(db_adapter)
        mock_pool.putconn.side_effect = TypeError("bad type")
        mock_conn.close.side_effect = TypeError("close bad")
        try:
            with db_adapter.get_db_connection() as (conn, cursor):
                pass
        finally:
            db_adapter._connection_pool = original


class TestModuleLevelImportFallbacks:
    """模块级 import fallback 路径 (lines 20-28, 41-57, 64-69)"""

    def test_psycopg2_import_error_fallback(self):
        import builtins
        import importlib
        import sys

        saved = {}
        keys_to_remove = [
            k
            for k in sys.modules
            if k.startswith("db_adapter") or k.startswith("psycopg2")
        ]
        for k in keys_to_remove:
            saved[k] = sys.modules.pop(k)

        orig_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "psycopg2" or name.startswith("psycopg2."):
                raise ImportError("no psycopg2")
            return orig_import(name, *args, **kwargs)

        try:
            builtins.__import__ = mock_import
            mod = importlib.import_module("db_adapter")
            assert mod.PSYCOPG2_AVAILABLE is False
            assert mod.psycopg2 is None
            assert mod.pool is None
        finally:
            builtins.__import__ = orig_import
            for k, v in saved.items():
                sys.modules[k] = v
            if "db_adapter" in sys.modules:
                sys.modules.pop("db_adapter")
            saved_mod = saved.get("db_adapter")
            if saved_mod:
                sys.modules["db_adapter"] = saved_mod

    def test_db_utils_import_error_fallback(self):
        import builtins
        import importlib
        import sys

        saved = {}
        keys_to_remove = [
            k for k in sys.modules if k == "db_adapter" or k == "db_utils"
        ]
        for k in keys_to_remove:
            saved[k] = sys.modules.pop(k)

        orig_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "db_utils" or name == ".db_utils":
                raise ImportError("no db_utils")
            return orig_import(name, *args, **kwargs)

        try:
            builtins.__import__ = mock_import
            mod = importlib.import_module("db_adapter")
            counter = mod._increment_connection_counter()
            assert counter == 0
            counter = mod._decrement_connection_counter()
            assert counter == 0
        finally:
            builtins.__import__ = orig_import
            for k, v in saved.items():
                sys.modules[k] = v
            if "db_adapter" in sys.modules:
                sys.modules.pop("db_adapter")
            saved_mod = saved.get("db_adapter")
            if saved_mod:
                sys.modules["db_adapter"] = saved_mod
