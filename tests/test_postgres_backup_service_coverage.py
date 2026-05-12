import importlib
import subprocess
from unittest.mock import MagicMock

import pytest

import postgres_backup_service as service_module
import postgres_backup_service_support as support_module


@pytest.fixture(autouse=True)
def patched_postgres_config():
    original = support_module.POSTGRES_CONFIG.copy()
    support_module.POSTGRES_CONFIG.clear()
    support_module.POSTGRES_CONFIG.update(
        {
            "host": "db-host",
            "port": 5433,
            "user": "db-user",
            "password": "db-pass",
            "database": "db-name",
            "options": "--role=test_role",
        }
    )
    yield
    support_module.POSTGRES_CONFIG.clear()
    support_module.POSTGRES_CONFIG.update(original)


@pytest.fixture
def backup_system(tmp_path, monkeypatch):
    monkeypatch.setattr(service_module, "ensure_postgres_bin_on_path", lambda: None)
    return service_module.PostgresBackupSystem(
        backup_dir=str(tmp_path),
        backup_interval_hours=1,
        max_backups=3,
    )


@pytest.fixture
def restored_service_module(monkeypatch):
    monkeypatch.setattr(support_module, "ensure_postgres_bin_on_path", lambda: None)
    module = importlib.reload(service_module)
    yield module
    importlib.reload(module)


def test_is_pg_dump_available_success_and_failures(backup_system):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            service_module.subprocess,
            "run",
            MagicMock(return_value=MagicMock(returncode=0)),
        )
        assert backup_system._is_pg_dump_available() is True

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            service_module.subprocess,
            "run",
            MagicMock(side_effect=FileNotFoundError()),
        )
        assert backup_system._is_pg_dump_available() is False

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            service_module.subprocess,
            "run",
            MagicMock(side_effect=subprocess.CalledProcessError(1, ["pg_dump"])),
        )
        assert backup_system._is_pg_dump_available() is False


def test_diagnose_reports_expected_flags(backup_system):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_is_pg_dump_available", lambda: True)
        monkeypatch.setattr(service_module.os.path, "exists", lambda path: True)
        monkeypatch.setattr(service_module.os, "access", lambda path, mode: True)
        monkeypatch.setattr(backup_system, "_is_database_connectable", lambda: False)
        assert backup_system.diagnose() == {
            "pg_dump_available": True,
            "backup_dir_exists": True,
            "db_connectable": False,
            "backup_dir_writable": True,
        }


def test_filter_backup_files_builds_sorted_records(backup_system):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            service_module.os,
            "listdir",
            lambda path: ["auto_backup_old.dump", "skip.txt", "manual_backup_new.dump"],
        )
        monkeypatch.setattr(
            backup_system,
            "_build_backup_record",
            MagicMock(
                side_effect=[
                    {"name": "auto_backup_old.dump", "path": "a", "size": 1, "mtime": 1, "type": "auto"},
                    {"name": "manual_backup_new.dump", "path": "b", "size": 2, "mtime": 2, "type": "manual"},
                ]
            ),
        )
        records = backup_system._filter_backup_files()

    assert [record["name"] for record in records] == [
        "manual_backup_new.dump",
        "auto_backup_old.dump",
    ]


def test_build_backup_record_and_get_backup_type(backup_system, tmp_path):
    backup_file = tmp_path / "pre_restore_backup_demo.dump"
    backup_file.write_bytes(b"abcd")
    record = backup_system._build_backup_record(backup_file.name)

    assert record is not None
    assert record["name"] == backup_file.name
    assert record["path"].endswith(backup_file.name)
    assert record["size"] == 4
    assert record["type"] == "snapshot"
    assert backup_system._get_backup_type("manual_backup_test.dump") == "manual"
    assert backup_system._get_backup_type("auto_backup_test.dump") == "auto"


def test_build_backup_record_returns_none_on_os_error(backup_system):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(service_module.os.path, "getsize", MagicMock(side_effect=OSError("gone")))
        assert backup_system._build_backup_record("missing.dump") is None


def test_get_backup_stats_and_delete_success_and_read_success(backup_system, tmp_path):
    backup_file = tmp_path / "manual_backup_keep.dump"
    payload = b"payload"
    backup_file.write_bytes(payload)
    record = {
        "name": backup_file.name,
        "path": str(backup_file),
        "size": len(payload),
        "mtime": 1,
        "type": "manual",
    }

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_filter_backup_files", lambda: [record])
        stats = backup_system.get_backup_stats()

    assert stats["count"] == 1
    assert stats["total_size_mb"] == 0.0
    assert backup_system.read_backup_file(backup_file.name, max_size_mb=1) == payload
    assert backup_system.delete_backup(backup_file.name) is True
    assert not backup_file.exists()


def test_start_auto_backup_noops_when_running(backup_system):
    backup_system.is_running = True
    backup_system.start_auto_backup()
    assert backup_system.is_running is True


def test_is_database_connectable_success(backup_system):
    conn = MagicMock()
    cursor = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    conn.cursor.return_value = cursor

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(service_module.psycopg2, "connect", MagicMock(return_value=conn))
        assert backup_system._is_database_connectable() is True

    cursor.close.assert_called_once_with()


def test_is_database_connectable_import_error_returns_false(backup_system):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            service_module.psycopg2,
            "connect",
            MagicMock(side_effect=ImportError("missing psycopg2")),
        )
        assert backup_system._is_database_connectable() is False


def test_is_database_connectable_unexpected_exception_returns_false(backup_system):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            service_module.psycopg2,
            "connect",
            MagicMock(side_effect=RuntimeError("boom")),
        )
        assert backup_system._is_database_connectable() is False


def test_run_pg_dump_builds_command_with_options(backup_system):
    run_mock = MagicMock(return_value=MagicMock(returncode=0, stdout="ok", stderr=""))
    pgpass_mock = MagicMock(return_value="C:/temp/pgpassfile")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(service_module.subprocess, "run", run_mock)
        monkeypatch.setattr(backup_system, "_build_pgpass_file", pgpass_mock)
        backup_system._run_pg_dump("target.dump")

    args = run_mock.call_args.kwargs
    assert run_mock.call_args.args[0] == [
        "pg_dump",
        "-h",
        "db-host",
        "-p",
        "5433",
        "-U",
        "db-user",
        "-F",
        "c",
        "-f",
        "target.dump",
        "-o",
        "--role=test_role",
        "db-name",
    ]
    assert args["env"]["PGPASSFILE"] == "C:/temp/pgpassfile"
    assert args["check"] is True
    assert args["capture_output"] is True
    assert args["text"] is True
    pgpass_mock.assert_called_once_with()


def test_create_backup_success_cleans_old_files(backup_system, tmp_path):
    backup_path = tmp_path / "auto_backup_1.dump"

    def write_backup(path):
        backup_path.write_bytes(b"backup")

    backup_system.cleanup_old_backups = MagicMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_build_backup_path", lambda prefix: str(backup_path))
        monkeypatch.setattr(backup_system, "_run_pg_dump", write_backup)
        monkeypatch.setattr(backup_system, "verify_backup", lambda path: True)
        assert backup_system._create_backup(backup_system.auto_prefix) is True

    assert backup_path.exists()
    backup_system.cleanup_old_backups.assert_called_once_with()


def test_create_backup_pg_dump_failure_deletes_failed_file(backup_system):
    delete_mock = MagicMock()
    error = subprocess.CalledProcessError(2, ["pg_dump"], stderr=b"bad dump")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_build_backup_path", lambda prefix: "broken.dump")
        monkeypatch.setattr(backup_system, "_run_pg_dump", MagicMock(side_effect=error))
        monkeypatch.setattr(backup_system, "_delete_failed_backup_file", delete_mock)
        assert backup_system._create_backup(backup_system.auto_prefix) is False

    delete_mock.assert_called_once_with("broken.dump")


def test_create_backup_verify_failure_removes_file(backup_system, tmp_path):
    backup_path = tmp_path / "auto_backup_verify.dump"

    def write_backup(path):
        backup_path.write_bytes(b"backup")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_build_backup_path", lambda prefix: str(backup_path))
        monkeypatch.setattr(backup_system, "_run_pg_dump", write_backup)
        monkeypatch.setattr(backup_system, "verify_backup", lambda path: False)
        assert backup_system._create_backup(backup_system.auto_prefix) is False

    assert not backup_path.exists()


def test_create_backup_file_not_found_returns_false(backup_system):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_build_backup_path", lambda prefix: "missing.dump")
        monkeypatch.setattr(
            backup_system,
            "_run_pg_dump",
            MagicMock(side_effect=FileNotFoundError("pg_dump")),
        )
        assert backup_system._create_backup(backup_system.auto_prefix) is False


def test_create_backup_permission_error_returns_false(backup_system):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_build_backup_path", lambda prefix: "denied.dump")
        monkeypatch.setattr(
            backup_system,
            "_run_pg_dump",
            MagicMock(side_effect=PermissionError("denied")),
        )
        assert backup_system._create_backup(backup_system.auto_prefix) is False


def test_delete_failed_backup_file_ignores_remove_errors(backup_system, tmp_path):
    backup_path = tmp_path / "failed.dump"
    backup_path.write_bytes(b"x")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(service_module.os.path, "exists", lambda path: True)
        monkeypatch.setattr(service_module.os, "remove", MagicMock(side_effect=OSError("locked")))
        backup_system._delete_failed_backup_file(str(backup_path))


def test_verify_backup_success_returns_true(backup_system, tmp_path):
    backup_path = tmp_path / "verify.dump"
    backup_path.write_bytes(b"data")
    run_mock = MagicMock(return_value=MagicMock(returncode=0, stderr=b""))

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(service_module.subprocess, "run", run_mock)
        assert backup_system.verify_backup(str(backup_path)) is True

    assert run_mock.call_args.args[0] == ["pg_restore", "--list", str(backup_path)]


def test_verify_backup_failure_returns_false(backup_system, tmp_path):
    backup_path = tmp_path / "invalid.dump"
    backup_path.write_bytes(b"data")
    error = subprocess.CalledProcessError(1, ["pg_restore"], stderr=b"not valid")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(service_module.subprocess, "run", MagicMock(side_effect=error))
        assert backup_system.verify_backup(str(backup_path)) is False


def test_cleanup_old_backups_deletes_excess_files(backup_system):
    records = [
        {"name": f"backup{i}.dump", "path": f"path{i}.dump", "size": 1, "mtime": i, "type": "auto"}
        for i in range(5)
    ]
    remove_mock = MagicMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_filter_backup_files", lambda: records)
        monkeypatch.setattr(service_module.os, "remove", remove_mock)
        backup_system.cleanup_old_backups()

    assert [call.args[0] for call in remove_mock.call_args_list] == ["path3.dump", "path4.dump"]


def test_cleanup_old_backups_handles_remove_and_top_level_errors(backup_system):
    records = [
        {"name": "backup1.dump", "path": "path1.dump", "size": 1, "mtime": 1, "type": "auto"},
        {"name": "backup2.dump", "path": "path2.dump", "size": 1, "mtime": 0, "type": "auto"},
        {"name": "backup3.dump", "path": "path3.dump", "size": 1, "mtime": -1, "type": "auto"},
        {"name": "backup4.dump", "path": "path4.dump", "size": 1, "mtime": -2, "type": "auto"},
    ]
    remove_mock = MagicMock(side_effect=[OSError("locked")])

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_filter_backup_files", lambda: records)
        monkeypatch.setattr(service_module.os, "remove", remove_mock)
        backup_system.cleanup_old_backups()
        monkeypatch.setattr(
            backup_system,
            "_filter_backup_files",
            MagicMock(side_effect=RuntimeError("scan failed")),
        )
        backup_system.cleanup_old_backups()


def test_create_backup_and_manual_backup_delegate_to_internal_method(backup_system):
    create_mock = MagicMock(side_effect=[True, False])

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_create_backup", create_mock)
        assert backup_system.create_backup() is True
        assert backup_system.manual_backup() is False

    assert create_mock.call_args_list[0].args == (backup_system.auto_prefix,)
    assert create_mock.call_args_list[1].args == (backup_system.manual_prefix,)


def test_list_backups_delegates_to_filter(backup_system):
    expected = [{"name": "x.dump", "path": "x.dump", "size": 1, "mtime": 1, "type": "auto"}]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_filter_backup_files", lambda: expected)
        assert backup_system.list_backups() == expected


def test_get_backup_file_path_rejects_traversal(backup_system):
    with pytest.raises(ValueError, match="非法备份文件名"):
        backup_system.get_backup_file_path("../evil.dump")


def test_read_backup_file_over_limit_raises_value_error(backup_system, tmp_path):
    backup_path = tmp_path / "big.dump"
    backup_path.write_bytes(b"x")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "get_backup_file_path", lambda name: str(backup_path))
        monkeypatch.setattr(service_module.os.path, "getsize", lambda path: 2 * 1024 * 1024)
        with pytest.raises(ValueError, match="超过 1MB 限制"):
            backup_system.read_backup_file("big.dump", max_size_mb=1)


def test_delete_backup_returns_false_when_remove_fails(backup_system, tmp_path):
    backup_path = tmp_path / "delete.dump"
    backup_path.write_bytes(b"data")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "get_backup_file_path", lambda name: str(backup_path))
        monkeypatch.setattr(service_module.os, "remove", MagicMock(side_effect=OSError("busy")))
        assert backup_system.delete_backup("delete.dump") is False


def test_start_auto_backup_creates_thread_and_runs_initial_backup(backup_system):
    thread = MagicMock()
    create_backup = MagicMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "create_backup", create_backup)
        monkeypatch.setattr(service_module, "load_schedule_module", lambda: None)
        monkeypatch.setattr(service_module.threading, "Thread", MagicMock(return_value=thread))
        backup_system.start_auto_backup()

    assert backup_system.is_running is True
    assert backup_system.backup_thread is thread
    create_backup.assert_called_once_with()
    thread.start.assert_called_once_with()


def test_build_auto_backup_target_returns_expected_callable(backup_system):
    assert backup_system._build_auto_backup_target(None) == backup_system._run_without_schedule
    target = backup_system._build_auto_backup_target(object())
    assert callable(target)


def test_run_with_schedule_executes_single_iteration(backup_system):
    class FakeJob:
        def __init__(self):
            self.tag_name = None
            self.bound = None

        @property
        def hours(self):
            return self

        def do(self, func):
            self.bound = func
            return self

        def tag(self, name):
            self.tag_name = name
            return self

    class FakeSchedule:
        def __init__(self, system):
            self.system = system
            self.job = FakeJob()
            self.cleared_tag = None
            self.pending_calls = 0

        def clear(self, tag=None):
            self.cleared_tag = tag

        def every(self, hours):
            self.hours_value = hours
            return self.job

        def run_pending(self):
            self.pending_calls += 1
            self.system.is_running = False

    schedule_module = FakeSchedule(backup_system)
    backup_system.is_running = True

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system._stop_event, "wait", lambda timeout: False)
        backup_system._run_with_schedule(schedule_module)

    assert schedule_module.cleared_tag == "postgres_backup"
    assert schedule_module.hours_value == 1
    assert schedule_module.job.bound == backup_system.create_backup
    assert schedule_module.job.tag_name == "postgres_backup"
    assert schedule_module.pending_calls == 1


def test_run_with_schedule_falls_back_without_schedule(backup_system):
    schedule_module = MagicMock()
    schedule_module.clear.side_effect = RuntimeError("bind failed")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_run_without_schedule", MagicMock())
        backup_system._run_with_schedule(schedule_module)
        backup_system._run_without_schedule.assert_called_once_with()


def test_run_without_schedule_executes_backup_once(backup_system):
    create_calls = []
    backup_system.is_running = True

    def create_once():
        create_calls.append("called")
        backup_system.is_running = False

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "create_backup", create_once)
        monkeypatch.setattr(service_module.time, "time", MagicMock(side_effect=[0, 3601]))
        monkeypatch.setattr(backup_system._stop_event, "wait", lambda timeout: False)
        backup_system._run_without_schedule()

    assert create_calls == ["called"]


def test_run_without_schedule_logs_exceptions_and_continues(backup_system):
    backup_system.is_running = True
    wait_calls = []

    def fail_once():
        raise RuntimeError("backup failed")

    def wait_and_stop(timeout):
        wait_calls.append(timeout)
        backup_system.is_running = False
        return False

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "create_backup", fail_once)
        monkeypatch.setattr(service_module.time, "time", MagicMock(side_effect=[0, 3601]))
        monkeypatch.setattr(backup_system._stop_event, "wait", wait_and_stop)
        backup_system._run_without_schedule()

    assert wait_calls == [60]


def test_stop_auto_backup_sets_event_and_joins_thread(backup_system):
    thread = MagicMock()
    backup_system.is_running = True
    backup_system.backup_thread = thread

    backup_system.stop_auto_backup()

    assert backup_system.is_running is False
    assert backup_system.backup_thread is None
    thread.join.assert_called_once_with(timeout=10)
    assert backup_system._stop_event.is_set() is True


def test_module_wrapper_functions_delegate_to_backup_system(restored_service_module):
    system = MagicMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(restored_service_module, "backup_system", system)
        monkeypatch.setattr(restored_service_module, "_get_auto_backup_settings", MagicMock(return_value={"enabled": True}))
        monkeypatch.setattr(restored_service_module, "_update_auto_backup_settings", MagicMock(return_value=True))
        monkeypatch.setattr(restored_service_module, "stop_backup_service", MagicMock())
        monkeypatch.setattr(restored_service_module, "start_backup_service", MagicMock())

        system.get_backup_file_path.return_value = "C:/safe/manual.dump"
        system.manual_backup.return_value = True
        system.get_backup_stats.return_value = {"count": 1}
        system.list_backups.return_value = ["a.dump"]
        system.verify_backup.return_value = True
        system.delete_backup.return_value = True
        system.read_backup_file.return_value = b"data"
        system.restore_from_backup.return_value = True

        assert restored_service_module.create_manual_backup() is True
        assert restored_service_module.get_backup_info() == {"count": 1}
        assert restored_service_module.list_backup_files() == ["a.dump"]
        assert restored_service_module.verify_backup_file("manual.dump") is True
        assert restored_service_module.delete_backup_file("manual.dump") is True
        assert restored_service_module.read_backup_file("manual.dump") == b"data"
        assert restored_service_module.restore_database("manual.dump", create_snapshot=False) is True
        assert restored_service_module.get_auto_backup_settings() == {"enabled": True}
        assert restored_service_module.update_auto_backup_settings(enabled=True, interval_hours=2, max_backups=4) is True

    system.manual_backup.assert_called_once_with()
    system.get_backup_stats.assert_called_once_with()
    system.list_backups.assert_called_once_with()
    system.get_backup_file_path.assert_called_once_with("manual.dump")
    system.verify_backup.assert_called_once_with("C:/safe/manual.dump")
    system.delete_backup.assert_called_once_with("manual.dump")
    system.read_backup_file.assert_called_once_with("manual.dump")
    system.restore_from_backup.assert_called_once_with("manual.dump", create_snapshot=False)


def test_start_backup_service_respects_enabled_flag(restored_service_module):
    system = MagicMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(restored_service_module, "backup_system", system)
        monkeypatch.setattr(restored_service_module, "get_auto_backup_settings", lambda: {"enabled": True, "interval_hours": 5})
        restored_service_module.start_backup_service()

    assert system.backup_interval_hours == 5
    system.start_auto_backup.assert_called_once_with()


def test_start_backup_service_skips_when_disabled(restored_service_module):
    system = MagicMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(restored_service_module, "backup_system", system)
        monkeypatch.setattr(restored_service_module, "get_auto_backup_settings", lambda: {"enabled": False, "interval_hours": 5})
        restored_service_module.start_backup_service()

    system.start_auto_backup.assert_not_called()


def test_stop_backup_service_calls_stop_auto_backup(restored_service_module):
    system = MagicMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(restored_service_module, "backup_system", system)
        restored_service_module.stop_backup_service()

    system.stop_auto_backup.assert_called_once_with()
