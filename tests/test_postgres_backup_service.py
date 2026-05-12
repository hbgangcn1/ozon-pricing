# -*- coding: utf-8 -*-
"""
postgres_backup_service.py 单元测试
测试不依赖真实数据库和 subprocess 的方法
"""
import pytest
import subprocess
from unittest.mock import MagicMock, patch, mock_open


class TestPostgresBackupSystemInit:
    """测试 PostgresBackupSystem 初始化"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_init_with_defaults(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        assert system.backup_dir == "backups/postgres"
        assert system.backup_interval_hours == 6
        assert system.max_backups == 28
        assert system.is_running is False

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_init_with_custom_values(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem(
            backup_dir="custom/backup",
            backup_interval_hours=12,
            max_backups=50,
        )
        assert system.backup_dir == "custom/backup"
        assert system.backup_interval_hours == 12
        assert system.max_backups == 50

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_backup_interval_hours_minimum_is_1(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem(backup_interval_hours=0)
        assert system.backup_interval_hours == 1


class TestBuildEnv:
    """测试 _build_env 方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_build_env_includes_pgpassword(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        env = system._build_env()
        assert "PGPASSWORD" not in env
        assert isinstance(env, dict)


class TestBuildFilename:
    """测试 _build_filename 方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_filename_contains_prefix(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        filename = system._build_filename("test_prefix")
        assert "test_prefix" in filename
        assert filename.endswith(".dump")

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_filename_contains_timestamp(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        import re
        system = PostgresBackupSystem()
        filename = system._build_filename("auto_backup")
        pattern = r"auto_backup_\d{8}_\d{6}\.dump"
        assert re.match(pattern, filename)


class TestBuildBackupPath:
    """测试 _build_backup_path 方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_backup_path_joins_dir_and_filename(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch.object(system, "_build_filename", return_value="test.dump"):
            path = system._build_backup_path("test")
            assert "test.dump" in path
            assert "backup" in path


class TestIsTrackedBackupFile:
    """测试 _is_tracked_backup_file 方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_auto_backup_is_tracked(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        assert system._is_tracked_backup_file("auto_backup_20240101_120000.dump") is True

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_manual_backup_is_tracked(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        assert system._is_tracked_backup_file("manual_backup_20240101_120000.dump") is True

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_prerestore_backup_is_tracked(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        assert system._is_tracked_backup_file("pre_restore_backup_20240101_120000.dump") is True

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_wrong_extension_is_not_tracked(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        assert system._is_tracked_backup_file("backup.txt") is False

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_untracked_prefix_not_tracked(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        assert system._is_tracked_backup_file("other_20240101_120000.dump") is False


class TestGetBackupType:
    """测试 _get_backup_type 方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_manual_prefix_returns_manual(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        assert system._get_backup_type("manual_backup_test.dump") == "manual"

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_prerestore_prefix_returns_snapshot(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        assert system._get_backup_type("pre_restore_backup_test.dump") == "snapshot"

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_auto_prefix_returns_auto(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        assert system._get_backup_type("auto_backup_test.dump") == "auto"


class TestBuildBackupRecord:
    """测试 _build_backup_record 方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_build_record_success(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch("os.path.getsize", return_value=1024):
            with patch("os.path.getmtime", return_value=1704067200):
                with patch.object(system, "_get_backup_type", return_value="auto"):
                    record = system._build_backup_record("auto_backup_test.dump")
                    assert record is not None
                    assert record["name"] == "auto_backup_test.dump"
                    assert record["size"] == 1024
                    assert record["type"] == "auto"

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_build_record_os_error_returns_none(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch("os.path.getsize", side_effect=OSError("File not found")):
            record = system._build_backup_record("nonexistent.dump")
            assert record is None


class TestFilterBackupFiles:
    """测试 _filter_backup_files 方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_filter_backup_files_sorts_by_mtime(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        from datetime import datetime
        system = PostgresBackupSystem()

        mock_records = [
            {
                "name": "auto_backup_old.dump",
                "path": "/old/path",
                "size": 100,
                "mtime": datetime(2020, 1, 1),
                "type": "auto",
            },
            {
                "name": "auto_backup_new.dump",
                "path": "/new/path",
                "size": 200,
                "mtime": datetime(2024, 1, 1),
                "type": "auto",
            },
        ]

        with patch("os.listdir", return_value=["auto_backup_old.dump", "auto_backup_new.dump"]):
            with patch.object(system, "_is_tracked_backup_file", return_value=True):
                with patch.object(system, "_build_backup_record", side_effect=mock_records):
                    records = system._filter_backup_files()
                    assert len(records) == 2
                    assert records[0]["name"] == "auto_backup_new.dump"
                    assert records[1]["name"] == "auto_backup_old.dump"


class TestDiagnose:
    """测试 diagnose 方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_diagnose_returns_status_dict(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch.object(system, "_is_pg_dump_available", return_value=True):
            with patch("os.path.exists", return_value=True):
                with patch("os.access", return_value=True):
                    with patch.object(system, "_is_database_connectable", return_value=True):
                        status = system.diagnose()
                        assert "pg_dump_available" in status
                        assert "backup_dir_exists" in status
                        assert "backup_dir_writable" in status
                        assert "db_connectable" in status


class TestIsPgDumpAvailable:
    """测试 _is_pg_dump_available 方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_pg_dump_available(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch("subprocess.run", return_value=MagicMock(returncode=0)):
            assert system._is_pg_dump_available() is True

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_pg_dump_not_available(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            assert system._is_pg_dump_available() is False

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_pg_dump_version_failed(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "pg_dump")):
            assert system._is_pg_dump_available() is False


class TestAutoBackupLifecycle:
    """测试自动备份生命周期方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_start_auto_backup_already_running(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        system.is_running = True
        with patch("postgres_backup_service.logger"):
            system.start_auto_backup()
            assert system.is_running is True

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_stop_auto_backup_not_running(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        system.is_running = False
        with patch("postgres_backup_service.logger"):
            system.stop_auto_backup()
            assert system.is_running is False


class TestBackupStats:
    """测试备份统计方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_get_backup_stats_returns_correct_structure(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch.object(system, "_filter_backup_files", return_value=[]):
            stats = system.get_backup_stats()
            assert "count" in stats
            assert "total_size_mb" in stats
            assert "files" in stats
            assert stats["count"] == 0
            assert stats["total_size_mb"] == 0


class TestDeleteBackup:
    """测试删除备份方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_delete_nonexistent_returns_false(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch("os.path.exists", return_value=False):
            with patch("postgres_backup_service.logger"):
                result = system.delete_backup("nonexistent.dump")
                assert result is False

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_delete_existing_returns_true(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch("os.path.exists", return_value=True):
            with patch("os.remove"):
                with patch("postgres_backup_service.logger"):
                    result = system.delete_backup("existing.dump")
                    assert result is True


class TestReadBackupFile:
    """测试读取备份文件方法"""

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_read_backup_file_too_large(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch("os.path.getsize", return_value=600 * 1024 * 1024):
            with pytest.raises(ValueError, match="备份文件过大"):
                system.read_backup_file("large.dump", max_size_mb=500)

    @patch("postgres_backup_service.ensure_postgres_bin_on_path")
    @patch("pathlib.Path.mkdir")
    def test_read_backup_file_success(self, mock_mkdir, mock_ensure):
        from postgres_backup_service import PostgresBackupSystem
        system = PostgresBackupSystem()
        with patch("os.path.getsize", return_value=1024):
            with patch("builtins.open", mock_open(read_data=b"backup data")):
                with patch.object(system, "get_backup_file_path", return_value="/path/backup.dump"):
                    data = system.read_backup_file("backup.dump")
                    assert data == b"backup data"
