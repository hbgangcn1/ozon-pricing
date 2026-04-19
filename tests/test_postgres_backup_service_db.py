# -*- coding: utf-8 -*-
"""
postgres_backup_service_db.py 单元测试
主要测试静态方法和纯逻辑函数，不依赖真实数据库
"""
import pytest
from unittest.mock import MagicMock, patch, mock_open


class TestHasFatalRestoreError:
    """测试 _has_fatal_restore_error 静态方法"""

    def test_empty_stderr_returns_false(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error("") is False
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(None) is False

    def test_permission_denied_is_non_fatal(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = 'pg_restore: [archiver] must be owner of extension pg_stat_statements'
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr) is False

    def test_does_not_exist_is_non_fatal(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = 'pg_restore: [archiver] ERROR: table "users" does not exist'
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr) is False

    def test_already_exists_is_non_fatal(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = 'pg_restore: [archiver] NOTICE: table "users" already exists'
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr) is False

    def test_role_is_non_fatal(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = 'pg_restore: [archiver] ERROR: role "postgres" does not exist'
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr) is False

    def test_chinese_permission_denied_is_non_fatal(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = '错误: 权限不够'
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr) is False

    def test_chinese_owner_is_non_fatal(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = '错误: 必须是 schema public 的属主'
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr) is False

    def test_chinese_not_exists_is_non_fatal(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = '错误: 表 "products" 不存在'
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr) is False

    def test_warning_lines_are_ignored(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = 'WARNING: this is just a warning\nERROR: table does not exist'
        result = PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr)
        assert result is False

    def test_real_error_is_fatal(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = 'ERROR: syntax error at or near "INVALID"'
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr) is True

    def test_connection_error_is_fatal(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = 'ERROR: could not connect to server: Connection refused'
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr) is True

    def test_malformed_backup_is_fatal(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = 'ERROR: file is not a valid archive'
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr) is True

    def test_mixed_output_with_real_error(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        stderr = 'WARNING: ignored\nERROR: out of memory\nsome notice'
        assert PostgresBackupDatabaseMixin._has_fatal_restore_error(stderr) is True


class TestBackupFileExists:
    """测试 _backup_file_exists 静态方法"""

    def test_existing_file_returns_true(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        with patch("builtins.open", mock_open(read_data=b"data")):
            with patch("os.path.exists", return_value=True):
                result = PostgresBackupDatabaseMixin._backup_file_exists("/path/to/backup.dump")
                assert result is True

    def test_nonexistent_file_returns_false(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        with patch("os.path.exists", return_value=False):
            result = PostgresBackupDatabaseMixin._backup_file_exists("/path/to/nonexistent.dump")
            assert result is False

    def test_os_error_returns_false(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        with patch("os.path.exists", side_effect=OSError("Permission denied")):
            result = PostgresBackupDatabaseMixin._backup_file_exists("/path/to/backup.dump")
            assert result is False


class TestCleanupRemainingObjects:
    """测试 _cleanup_remaining_objects 静态方法"""

    def test_no_tables_returns_zero(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        mock_cur = MagicMock()
        mock_cur.fetchall.side_effect = [
            [],  # tables
            [],  # sequences
            [],  # types
        ]
        result = PostgresBackupDatabaseMixin._cleanup_remaining_objects(mock_cur)
        assert result == 0

    def test_all_tables_dropped(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        mock_cur = MagicMock()
        mock_cur.fetchall.side_effect = [
            [("table1",), ("table2",)],  # tables
            [],  # sequences
            [],  # types
        ]
        result = PostgresBackupDatabaseMixin._cleanup_remaining_objects(mock_cur)
        assert result == 0
        assert mock_cur.execute.call_count >= 4

    def test_tables_truncated_on_drop_failure(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        from psycopg2 import Error as Psycopg2Error

        mock_cur = MagicMock()
        tables_and_sequences_and_types = [
            [("table1",)],
            [],
            [],
        ]
        mock_cur.fetchall.side_effect = tables_and_sequences_and_types

        original_execute = mock_cur.execute.side_effect = []
        call_count = [0]

        def execute_side_effect(*args):
            call_count[0] += 1
            sql_str = str(args[0]) if args else ""
            if "DROP TABLE" in sql_str:
                raise Psycopg2Error("permission denied")
            elif "TRUNCATE TABLE" in sql_str:
                pass
            elif "SELECT" in sql_str:
                pass

        mock_cur.execute.side_effect = execute_side_effect

        result = PostgresBackupDatabaseMixin._cleanup_remaining_objects(mock_cur)
        assert result >= 0


class TestCanDropPublicSchema:
    """测试 _can_drop_public_schema 静态方法"""

    def test_superuser_returns_true(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [
            ("test_user",),  # current_user
            (True,),  # is superuser
        ]
        result = PostgresBackupDatabaseMixin._can_drop_public_schema(mock_cur)
        assert result is True

    def test_schema_owner_returns_true(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [
            ("test_user",),  # current_user
            (False,),  # not superuser
            ("test_user",),  # owner equals current_user
        ]
        result = PostgresBackupDatabaseMixin._can_drop_public_schema(mock_cur)
        assert result is True

    def test_not_owner_returns_false(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [
            ("test_user",),  # current_user
            (False,),  # not superuser
            ("other_user",),  # owner does not equal current_user
        ]
        result = PostgresBackupDatabaseMixin._can_drop_public_schema(mock_cur)
        assert result is False

    def test_exception_returns_false(self):
        from postgres_backup_service_db import PostgresBackupDatabaseMixin
        mock_cur = MagicMock()
        mock_cur.execute.side_effect = Exception("Database error")
        result = PostgresBackupDatabaseMixin._can_drop_public_schema(mock_cur)
        assert result is False
