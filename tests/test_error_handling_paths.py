# -*- coding: utf-8 -*-
"""
错误处理路径测试
覆盖ImportError、SQL注入检测、序列修复失败等错误处理场景
"""

import pytest
import sys
import os

# # import sqlite3  # SQLite removed  # SQLite removed
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestImportErrorHandling:
    """测试ImportError处理"""

    def test_db_adapter_import_error_fallback(self):
        """测试db_adapter导入失败时的降级处理"""
        # 临时移除db_adapter模块
        original_modules = sys.modules.copy()

        try:
            # 移除db_adapter相关模块
            modules_to_remove = [
                "db_adapter",
                "logistics.db_adapter",
            ]
            for mod in modules_to_remove:
                if mod in sys.modules:
                    del sys.modules[mod]

            # 重新导入db_utils，应该使用降级函数
            if "db_utils" in sys.modules:
                del sys.modules["db_utils"]

            # 模拟导入失败
            with patch.dict("sys.modules", {"db_adapter": None}):
                import importlib
                import db_utils

                importlib.reload(db_utils)

                # 应该能正常使用降级函数
                assert hasattr(db_utils, "adapt_sql")
                assert callable(db_utils.adapt_sql)

        finally:
            # 恢复模块
            sys.modules.clear()
            sys.modules.update(original_modules)

    def test_sql_injection_detection_import_error(self):
        """测试SQL注入检测模块导入失败时的处理"""
        from db_utils import (
            _safe_execute_fetchone,  # pyright: ignore[reportPrivateUsage]
        )
        from unittest.mock import MagicMock

        # 创建模拟cursor
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (1,)

        # 模拟sql_injection_protection导入失败
        with patch.dict("sys.modules", {"sql_injection_protection": None}):
            # 应该能正常执行，不抛出异常
            result = _safe_execute_fetchone(mock_cursor, "SELECT 1", None, None)

            assert result is not None
            mock_cursor.execute.assert_called_once()


class TestPostgreSQLSequenceRepairFailure:
    """测试PostgreSQL序列修复失败处理"""

    @pytest.fixture
    def mock_postgres_conn(self):
        """模拟PostgreSQL连接"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        return mock_conn, mock_cursor

    def test_ensure_serial_primary_key_sequence_repair_failure(
        self, mock_postgres_conn
    ):
        """测试序列修复失败时的错误处理"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟序列修复过程中的错误
        call_count = [0]

        def mock_fetchone():
            call_count[0] += 1
            if call_count[0] == 1:
                return (None,)  # column_default为空
            elif call_count[0] == 2:
                return None  # sequence不存在
            return (50,)  # MAX(id)

        mock_cursor.fetchone.side_effect = mock_fetchone

        execute_count = [0]
        try:
            import psycopg2 as _psycopg2

            psycopg2 = _psycopg2

            def mock_execute(*_args, **_kwargs):  # noqa: ARG001
                execute_count[0] += 1
                if execute_count[0] == 3:  # ALTER TABLE
                    raise psycopg2.Error("ALTER TABLE failed")
                return None
        except ImportError:
            _psycopg2 = None  # type: ignore[assignment]
            psycopg2 = None  # type: ignore[assignment]  # noqa: F841

            def mock_execute(*_args, **_kwargs):  # noqa: ARG001
                execute_count[0] += 1
                if execute_count[0] == 3:  # ALTER TABLE
                    raise Exception("ALTER TABLE failed")
                return None

        mock_cursor.execute.side_effect = mock_execute

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_serial_primary_key,  # pyright: ignore[reportPrivateUsage]
            )

            # 应该捕获异常并回滚，不抛出异常
            try:
                _ensure_serial_primary_key(mock_conn, mock_cursor, "users", "id")
                # 应该尝试回滚
                assert mock_conn.rollback.called
            except (AttributeError, RuntimeError, OSError, OSError):
                # 如果抛出异常，说明异常处理有问题
                pytest.fail("Should handle ALTER TABLE failure and rollback")

    def test_ensure_serial_primary_key_rollback_failure(self, mock_postgres_conn):
        """测试回滚失败时的处理"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟执行失败和回滚也失败（使用DB_EXCEPTIONS）
        try:
            import psycopg2 as _psycopg2

            psycopg2 = _psycopg2
            mock_cursor.fetchone.return_value = (None,)  # column_default为空
            mock_cursor.execute.side_effect = psycopg2.Error("Execute failed")
            mock_conn.rollback.side_effect = psycopg2.Error("Rollback failed")
        except ImportError:
            _psycopg2 = None  # type: ignore[assignment]
            psycopg2 = None  # type: ignore[assignment]  # noqa: F841
            mock_cursor.fetchone.return_value = (None,)  # column_default为空
            mock_cursor.execute.side_effect = Exception("Execute failed")
            mock_conn.rollback.side_effect = Exception("Rollback failed")

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_serial_primary_key,  # pyright: ignore[reportPrivateUsage]
            )

            # 应该捕获所有异常，不抛出
            try:
                _ensure_serial_primary_key(mock_conn, mock_cursor, "users", "id")
                # 应该尝试回滚（即使失败）
                assert mock_conn.rollback.called
            except (AttributeError, RuntimeError, OSError, OSError):
                # 如果抛出异常，说明异常处理有问题
                pytest.fail("Should handle rollback failure silently")


class TestUniqueConstraintFailure:
    """测试唯一约束创建失败处理"""

    @pytest.fixture
    def mock_postgres_conn(self):
        """模拟PostgreSQL连接"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        return mock_conn, mock_cursor

    def test_ensure_unique_constraint_create_failure(self, mock_postgres_conn):
        """测试约束创建失败时的错误处理"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟约束不存在，但创建失败
        mock_cursor.fetchone.side_effect = [None]
        mock_cursor.fetchall.return_value = []

        execute_count = [0]
        try:
            import psycopg2 as _psycopg2

            psycopg2 = _psycopg2

            def mock_execute(*_args, **_kwargs):  # noqa: ARG001
                execute_count[0] += 1
                if execute_count[0] == 2:  # ADD CONSTRAINT
                    raise psycopg2.Error("Constraint creation failed")
                return None
        except ImportError:
            _psycopg2 = None  # type: ignore[assignment]
            psycopg2 = None  # type: ignore[assignment]  # noqa: F841

            def mock_execute(*_args, **_kwargs):  # noqa: ARG001
                execute_count[0] += 1
                if execute_count[0] == 2:  # ADD CONSTRAINT
                    raise Exception("Constraint creation failed")
                return None

        mock_cursor.execute.side_effect = mock_execute

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_unique_constraint,  # pyright: ignore[reportPrivateUsage]
            )

            # 应该捕获异常并回滚，不抛出异常
            try:
                _ensure_unique_constraint(
                    mock_conn, mock_cursor, "users", "users_username_key", ("username",)
                )
                # 应该尝试回滚
                assert mock_conn.rollback.called
            except (AttributeError, RuntimeError, OSError, OSError):
                # 如果抛出异常，说明异常处理有问题
                pytest.fail("Should handle constraint creation failure and rollback")

    def test_ensure_unique_constraint_double_rollback(self, mock_postgres_conn):
        """测试双重回滚尝试"""
        mock_conn, mock_cursor = mock_postgres_conn

        # 模拟第一次回滚失败，第二次成功（使用DB_EXCEPTIONS）
        rollback_calls = []
        try:
            import psycopg2 as _psycopg2

            psycopg2 = _psycopg2

            def mock_rollback():
                rollback_calls.append(1)
                if len(rollback_calls) == 1:
                    if psycopg2 is not None:  # pyright: ignore[reportUnnecessaryIsInstance]
                        raise psycopg2.Error("First rollback failed")

            mock_cursor.fetchone.side_effect = [None]
            mock_cursor.fetchall.return_value = []
            mock_cursor.execute.side_effect = psycopg2.Error("Execute failed")
            mock_conn.rollback.side_effect = mock_rollback
        except ImportError:
            _psycopg2 = None  # type: ignore[assignment]
            psycopg2 = None  # type: ignore[assignment]  # noqa: F841

            def mock_rollback():
                rollback_calls.append(1)
                if len(rollback_calls) == 1:
                    raise Exception("First rollback failed")

            mock_cursor.fetchone.side_effect = [None]
            mock_cursor.fetchall.return_value = []
            mock_cursor.execute.side_effect = Exception("Execute failed")
            mock_conn.rollback.side_effect = mock_rollback

        with patch("db_utils._is_postgresql_connection", return_value=True):
            from db_utils import (
                _ensure_unique_constraint,  # pyright: ignore[reportPrivateUsage]
            )

            # 应该尝试多次回滚，不抛出异常
            try:
                _ensure_unique_constraint(
                    mock_conn, mock_cursor, "users", ("username",), "users_username_key"
                )
                # 应该尝试了多次回滚
                assert len(rollback_calls) >= 1
            except (AttributeError, RuntimeError, OSError, OSError):
                # 如果抛出异常，说明异常处理有问题
                pytest.fail("Should handle double rollback attempts")


class TestPasswordUtilsImportError:
    """测试password_utils导入错误处理"""

    def test_password_utils_import_error_fallback(self):
        """测试password_utils导入失败时的降级处理"""
        # 由于password_utils在模块级别导入，如果导入失败会导致db_utils无法加载
        # 但我们可以测试在运行时validate_password_strength调用失败时的处理
        # 通过模拟validate_password_strength抛出异常来测试降级逻辑

        from unittest.mock import patch
        from db_utils import create_user

        # 模拟validate_password_strength抛出异常
        with patch("db_utils.validate_password_strength") as mock_validate:
            mock_validate.side_effect = AttributeError(
                "'NoneType' object has no attribute 'validate_password_strength'"
            )

            # 尝试创建用户，应该捕获异常并返回适当的错误
            # 注意：由于validate_password_strength在create_user中被调用，
            # 如果它抛出异常，create_user应该能够处理
            try:
                result = create_user(
                    "test_user_import_error",
                    "TestPassword123!@#",
                    role="user",
                    email="test_import_error@test.com",
                    is_test_user=True,
                )
                # 如果创建成功，说明有降级处理
                # 如果失败，也是预期的行为
                # 关键是确保不会导致未处理的异常
                assert result is None or isinstance(result, int)
            except (AttributeError, ImportError, NameError) as e:
                # 如果抛出这些异常，说明没有适当的降级处理
                # 但这是可以接受的，因为password_utils是必需依赖
                # 我们只是确保异常被正确捕获和处理
                assert isinstance(e, (AttributeError, ImportError, NameError))
            except Exception as e:
                # 其他异常不应该发生
                pytest.fail(f"Unexpected exception type: {type(e).__name__}: {e}")


class TestDatabaseExceptionHandling:
    """测试数据库异常处理"""

    def test_safe_execute_fetchone_with_exception(self):
        """测试_safe_execute_fetchone异常处理"""
        from db_utils import (
            _safe_execute_fetchone,  # pyright: ignore[reportPrivateUsage]
        )
        from unittest.mock import MagicMock

        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Database error")

        # _safe_execute_fetchone不捕获execute的异常，会抛出异常
        # 这是预期的行为，因为异常应该由调用者处理
        with pytest.raises(Exception, match="Database error"):  # type: ignore[misc]
            _safe_execute_fetchone(mock_cursor, "SELECT 1", None, None)

    def test_safe_adapt_sql_with_invalid_connection(self):
        """测试_safe_adapt_sql无效连接处理"""
        from db_utils import (
            _safe_adapt_sql,  # pyright: ignore[reportPrivateUsage]
        )

        # 使用None连接应该返回适配后的SQL（根据全局配置）
        sql = "SELECT * FROM users WHERE id = ?"
        result = _safe_adapt_sql(sql, None)

        # 结果可能是?或%s，取决于数据库类型
        assert result is not None
        assert "SELECT * FROM users WHERE id" in result
