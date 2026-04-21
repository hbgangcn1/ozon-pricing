import sys
import types
import subprocess
from unittest.mock import MagicMock, call

import pytest
from psycopg2 import Error as PsycopgError

import postgres_backup_service_db as db_module


class DummyBackupSystem(db_module.PostgresBackupDatabaseMixin):
    def __init__(self):
        self.verify_result = True
        self.create_result = True
        self.paths = {}

    def _build_env(self) -> dict[str, str]:
        return {"PGPASSWORD": "secret"}

    def get_backup_file_path(self, backup_filename: str) -> str:
        return self.paths.get(backup_filename, backup_filename)

    def _create_backup(self, prefix: str) -> bool:
        return self.create_result

    def verify_backup(self, backup_path: str) -> bool:
        return self.verify_result

    def call_base_build_env(self):
        return super()._build_env()

    def call_base_get_backup_file_path(self, backup_filename: str):
        return super().get_backup_file_path(backup_filename)

    def call_base_create_backup(self, prefix: str):
        return super()._create_backup(prefix)

    def call_base_verify_backup(self, backup_path: str):
        return super().verify_backup(backup_path)

    @staticmethod
    def call_cleanup_remaining_objects(cur):
        return db_module.PostgresBackupDatabaseMixin._cleanup_remaining_objects(cur)

    @staticmethod
    def call_can_drop_public_schema(cur):
        return db_module.PostgresBackupDatabaseMixin._can_drop_public_schema(cur)


@pytest.fixture(autouse=True)
def patched_postgres_config():
    original = db_module.POSTGRES_CONFIG.copy()
    db_module.POSTGRES_CONFIG.clear()
    db_module.POSTGRES_CONFIG.update(
        {
            "host": "db-host",
            "port": 5433,
            "user": "db-user",
            "password": "db-pass",
            "database": "appdb",
            "options": "--role=test_role",
        }
    )
    yield
    db_module.POSTGRES_CONFIG.clear()
    db_module.POSTGRES_CONFIG.update(original)


@pytest.fixture
def backup_system():
    return DummyBackupSystem()


def make_connection(cursor=None):
    cur = cursor or MagicMock()
    cursor_cm = MagicMock()
    cursor_cm.__enter__.return_value = cur
    cursor_cm.__exit__.return_value = False
    conn = MagicMock()
    conn.cursor.return_value = cursor_cm
    conn.close = MagicMock()
    return conn, cur


def composed_text(call):
    return repr(call.args[0])


def test_abstract_methods_raise_not_implemented():
    mixin = DummyBackupSystem()

    with pytest.raises(NotImplementedError):
        mixin.call_base_build_env()
    with pytest.raises(NotImplementedError):
        mixin.call_base_get_backup_file_path("backup.dump")
    with pytest.raises(NotImplementedError):
        mixin.call_base_create_backup("prefix")
    with pytest.raises(NotImplementedError):
        mixin.call_base_verify_backup("backup.dump")


def test_run_pg_restore_success(backup_system):
    result = MagicMock(returncode=0, stdout="done", stderr="")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_reset_public_schema", MagicMock())
        monkeypatch.setattr(db_module.subprocess, "run", MagicMock(return_value=result))
        backup_system._run_pg_restore("backup.dump")


def test_run_pg_restore_raises_for_fatal_error(backup_system):
    result = MagicMock(returncode=1, stdout="", stderr="ERROR: syntax error")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_reset_public_schema", MagicMock())
        monkeypatch.setattr(db_module.subprocess, "run", MagicMock(return_value=result))
        with pytest.raises(subprocess.CalledProcessError):
            backup_system._run_pg_restore("backup.dump")


def test_run_pg_restore_allows_non_fatal_warning(backup_system):
    result = MagicMock(returncode=1, stdout="", stderr="ERROR: permission denied")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_reset_public_schema", MagicMock())
        monkeypatch.setattr(db_module.subprocess, "run", MagicMock(return_value=result))
        backup_system._run_pg_restore("backup.dump")


def test_reset_public_schema_drop_and_recreate(backup_system):
    conn, cur = make_connection()
    cur.fetchall.return_value = [("archive",), ("custom",)]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.psycopg2, "connect", MagicMock(return_value=conn))
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        monkeypatch.setattr(backup_system, "_can_drop_public_schema", lambda cursor: True)
        backup_system._reset_public_schema()

    texts = [composed_text(call) for call in cur.execute.call_args_list if call.args]
    assert any("DROP SCHEMA" in text and "archive" in text for text in texts)
    assert any("DROP SCHEMA" in text and "custom" in text for text in texts)
    assert any(call.args[0] == "DROP SCHEMA public CASCADE" for call in cur.execute.call_args_list)
    assert any(call.args[0] == "CREATE SCHEMA public" for call in cur.execute.call_args_list)


def test_reset_public_schema_falls_back_to_drop_owned(backup_system):
    conn, cur = make_connection()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = ("app_user",)
    cleanup_mock = MagicMock(return_value=2)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.psycopg2, "connect", MagicMock(return_value=conn))
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        monkeypatch.setattr(backup_system, "_can_drop_public_schema", lambda cursor: False)
        monkeypatch.setattr(backup_system, "_cleanup_remaining_objects", cleanup_mock)
        backup_system._reset_public_schema()

    texts = [composed_text(call) for call in cur.execute.call_args_list if call.args]
    assert any("DROP OWNED BY" in text and "app_user" in text for text in texts)
    cleanup_mock.assert_called_once_with(cur)


def test_reset_public_schema_raises_on_connection_error(backup_system):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            db_module.psycopg2,
            "connect",
            MagicMock(side_effect=PsycopgError("connect failed")),
        )
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        with pytest.raises(PsycopgError):
            backup_system._reset_public_schema()


def test_cleanup_remaining_objects_handles_drop_truncate_sequences_and_types():
    cur = MagicMock()
    cur.fetchall.side_effect = [
        [("drop_me",), ("truncate_me",), ("fail_me",)],
        [("seq1",)],
        [("enum1",)],
    ]

    def execute(statement, *args):
        text = repr(statement)
        if "DROP TABLE" in text and "truncate_me" in text:
            raise PsycopgError("drop failed")
        if "DROP TABLE" in text and "fail_me" in text:
            raise PsycopgError("drop failed")
        if "TRUNCATE TABLE" in text and "fail_me" in text:
            raise PsycopgError("truncate failed")
        if "DROP SEQUENCE" in text:
            raise PsycopgError("seq failed")
        if "DROP TYPE" in text:
            raise PsycopgError("type failed")

    cur.execute.side_effect = execute
    assert DummyBackupSystem.call_cleanup_remaining_objects(cur) == 1


def test_cleanup_remaining_objects_returns_zero_without_tables():
    cur = MagicMock()
    cur.fetchall.return_value = []
    assert DummyBackupSystem.call_cleanup_remaining_objects(cur) == 0


def test_drop_all_foreign_keys_success_and_inner_error(backup_system):
    conn, cur = make_connection()
    cur.fetchall.return_value = [
        ("public", "orders", "fk_ok"),
        ("public", "payments", "fk_fail"),
    ]

    def execute(statement, *args):
        if "fk_fail" in repr(statement):
            raise PsycopgError("cannot drop")

    cur.execute.side_effect = execute

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.psycopg2, "connect", MagicMock(return_value=conn))
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        backup_system._drop_all_foreign_keys()


def test_drop_all_foreign_keys_no_constraints_and_outer_error(backup_system):
    conn, cur = make_connection()
    cur.fetchall.return_value = []

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.psycopg2, "connect", MagicMock(return_value=conn))
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        backup_system._drop_all_foreign_keys()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            db_module.psycopg2,
            "connect",
            MagicMock(side_effect=PsycopgError("outer fail")),
        )
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        with pytest.raises(PsycopgError):
            backup_system._drop_all_foreign_keys()


def test_drop_sequence_dependencies_success_and_inner_error(backup_system):
    conn, cur = make_connection()
    cur.fetchall.return_value = [
        ("public", "users", "id", "nextval('users_id_seq'::regclass)"),
        ("public", "orders", "id", "nextval('orders_id_seq'::regclass)"),
    ]

    def execute(statement, *args):
        if "orders" in repr(statement):
            raise PsycopgError("cannot drop default")

    cur.execute.side_effect = execute

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.psycopg2, "connect", MagicMock(return_value=conn))
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        backup_system._drop_sequence_dependencies()


def test_drop_sequence_dependencies_no_rows_and_outer_error(backup_system):
    conn, cur = make_connection()
    cur.fetchall.return_value = []

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.psycopg2, "connect", MagicMock(return_value=conn))
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        backup_system._drop_sequence_dependencies()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            db_module.psycopg2,
            "connect",
            MagicMock(side_effect=PsycopgError("outer fail")),
        )
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        with pytest.raises(PsycopgError):
            backup_system._drop_sequence_dependencies()


def test_count_active_connections_returns_value(backup_system):
    cur = MagicMock()
    cur.fetchone.return_value = (3,)
    assert backup_system._count_active_connections(cur) == 3


def test_terminate_active_connections_handles_zero_active(backup_system):
    conn, _ = make_connection()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.psycopg2, "connect", MagicMock(return_value=conn))
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        monkeypatch.setattr(backup_system, "_count_active_connections", MagicMock(return_value=0))
        backup_system._terminate_active_connections()


def test_terminate_active_connections_waits_until_closed(backup_system):
    conn, cur = make_connection()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.psycopg2, "connect", MagicMock(return_value=conn))
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        monkeypatch.setattr(backup_system, "_count_active_connections", MagicMock(side_effect=[2, 1, 0]))
        monkeypatch.setattr(db_module.time, "sleep", MagicMock())
        backup_system._terminate_active_connections()

    assert any("pg_terminate_backend" in call.args[0] for call in cur.execute.call_args_list if isinstance(call.args[0], str))


def test_terminate_active_connections_permission_denied_is_ignored(backup_system):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            db_module.psycopg2,
            "connect",
            MagicMock(side_effect=PsycopgError("permission denied")),
        )
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        backup_system._terminate_active_connections()


def test_terminate_active_connections_warns_when_remaining(backup_system):
    conn, _ = make_connection()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.psycopg2, "connect", MagicMock(return_value=conn))
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        monkeypatch.setattr(backup_system, "_count_active_connections", MagicMock(side_effect=[2] + [1] * 11))
        monkeypatch.setattr(db_module.time, "sleep", MagicMock())
        backup_system._terminate_active_connections()


def test_reinitialize_connection_pool_success(backup_system, monkeypatch):
    dispose = MagicMock()
    fake_engine = types.SimpleNamespace(sync_engine=types.SimpleNamespace(dispose=dispose))
    monkeypatch.setitem(sys.modules, "database", types.SimpleNamespace(engine=fake_engine))
    monkeypatch.setattr(db_module.time, "sleep", MagicMock())
    backup_system._reinitialize_connection_pool()
    dispose.assert_called_once_with()


def test_reinitialize_connection_pool_handles_exception(backup_system, monkeypatch):
    monkeypatch.setitem(sys.modules, "database", types.SimpleNamespace())
    backup_system._reinitialize_connection_pool()


def test_verify_restored_tables_success_and_connection_failure(backup_system):
    success_conn, success_cur = make_connection()
    success_cur.fetchall.return_value = [("logistics",), ("products",), ("users",)]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.psycopg2, "connect", MagicMock(return_value=success_conn))
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        backup_system._verify_restored_tables()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            db_module.psycopg2,
            "connect",
            MagicMock(side_effect=PsycopgError("offline")),
        )
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        backup_system._verify_restored_tables()


def test_verify_restored_tables_raises_when_missing(backup_system):
    conn, cur = make_connection()
    cur.fetchall.return_value = [("users",), ("products",)]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.psycopg2, "connect", MagicMock(return_value=conn))
        monkeypatch.setattr(db_module, "build_postgres_dsn", lambda database=None: "dsn")
        with pytest.raises(RuntimeError, match="恢复后缺少关键表: logistics"):
            backup_system._verify_restored_tables()


def test_validate_restore_backup_branches(backup_system, tmp_path):
    backup_file = tmp_path / "restore.dump"
    backup_file.write_bytes(b"data")
    backup_system.verify_result = True

    assert backup_system._validate_restore_backup(backup_file.name, str(backup_file)) is True

    backup_system.verify_result = False
    assert backup_system._validate_restore_backup(backup_file.name, str(backup_file)) is False

    backup_system.verify_result = True
    assert backup_system._validate_restore_backup(backup_file.name, str(backup_file) + ".missing") is False


def test_prepare_restore_handles_snapshot_creation_result(backup_system, tmp_path):
    backup_file = tmp_path / "restore.dump"
    backup_file.write_bytes(b"data")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_validate_restore_backup", MagicMock(return_value=False))
        assert backup_system._prepare_restore(backup_file.name, str(backup_file), True) is False

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_validate_restore_backup", MagicMock(return_value=True))
        monkeypatch.setattr(backup_system, "_create_backup", MagicMock(return_value=False))
        assert backup_system._prepare_restore(backup_file.name, str(backup_file), True) is True


def test_terminate_restore_connections_always_sleeps(backup_system):
    sleep_mock = MagicMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_terminate_active_connections", MagicMock(side_effect=RuntimeError("no rights")))
        monkeypatch.setattr(db_module.time, "sleep", sleep_mock)
        backup_system._terminate_restore_connections()

    sleep_mock.assert_called_once_with(1)


def test_restore_attempt_success(backup_system):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_run_pg_restore", MagicMock())
        monkeypatch.setattr(backup_system, "_reinitialize_connection_pool", MagicMock())
        monkeypatch.setattr(backup_system, "_verify_restored_tables", MagicMock())
        monkeypatch.setattr(db_module.time, "sleep", MagicMock())
        assert backup_system._restore_attempt("backup.dump", "backup.dump", 1, 3) is True


def test_restore_attempt_handles_subprocess_and_generic_errors(backup_system):
    error = subprocess.CalledProcessError(1, ["pg_restore"], stderr=b"broken")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_run_pg_restore", MagicMock(side_effect=error))
        monkeypatch.setattr(backup_system, "_handle_restore_subprocess_error", MagicMock())
        assert backup_system._restore_attempt("backup.dump", "backup.dump", 1, 3) is False

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_run_pg_restore", MagicMock(side_effect=RuntimeError("boom")))
        monkeypatch.setattr(backup_system, "_sleep_before_retry", MagicMock())
        assert backup_system._restore_attempt("backup.dump", "backup.dump", 1, 3) is False


def test_can_drop_public_schema_paths():
    cur = MagicMock()
    cur.fetchone.side_effect = [("app_user",), (True,)]
    assert DummyBackupSystem.call_can_drop_public_schema(cur) is True

    cur = MagicMock()
    cur.fetchone.side_effect = [("app_user",), (False,), ("app_user",)]
    assert DummyBackupSystem.call_can_drop_public_schema(cur) is True

    cur = MagicMock()
    cur.fetchone.side_effect = [("app_user",), (False,), ("other_user",)]
    assert DummyBackupSystem.call_can_drop_public_schema(cur) is False

    cur = MagicMock()
    cur.execute.side_effect = RuntimeError("boom")
    assert DummyBackupSystem.call_can_drop_public_schema(cur) is False


def test_handle_restore_subprocess_error_retries_and_final_failure(backup_system):
    sleep_mock = MagicMock()
    exc = subprocess.CalledProcessError(1, ["pg_restore"], stderr=b"bad archive")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.time, "sleep", sleep_mock)
        monkeypatch.setattr(backup_system, "_terminate_active_connections", MagicMock())
        backup_system._handle_restore_subprocess_error(exc, 1, 3)

    assert sleep_mock.call_args_list == [call(2), call(1)]

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.time, "sleep", MagicMock())
        monkeypatch.setattr(
            backup_system,
            "_terminate_active_connections",
            MagicMock(side_effect=PsycopgError("permission denied")),
        )
        backup_system._handle_restore_subprocess_error(exc, 2, 3)

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.time, "sleep", MagicMock())
        monkeypatch.setattr(backup_system, "_terminate_active_connections", MagicMock())
        backup_system._handle_restore_subprocess_error(exc, 3, 3)


def test_handle_restore_subprocess_error_accepts_string_stderr(backup_system):
    exc = subprocess.CalledProcessError(1, ["pg_restore"], stderr="plain error")

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.time, "sleep", MagicMock())
        monkeypatch.setattr(backup_system, "_terminate_active_connections", MagicMock())
        backup_system._handle_restore_subprocess_error(exc, 3, 3)


def test_sleep_before_retry_branches(backup_system):
    sleep_mock = MagicMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(db_module.time, "sleep", sleep_mock)
        backup_system._sleep_before_retry(1, 3)
        backup_system._sleep_before_retry(3, 3)

    sleep_mock.assert_called_once_with(2)


def test_restore_from_backup_success_and_validation_failure(backup_system):
    backup_system.paths = {"good.dump": "good.dump", "bad.dump": "bad.dump"}
    prepare_mock = MagicMock(side_effect=[True, False])
    terminate_mock = MagicMock()
    restore_mock = MagicMock(side_effect=[True])

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_prepare_restore", prepare_mock)
        monkeypatch.setattr(backup_system, "_terminate_restore_connections", terminate_mock)
        monkeypatch.setattr(backup_system, "_restore_attempt", restore_mock)
        assert backup_system.restore_from_backup("good.dump", create_snapshot=False) is True
        assert backup_system.restore_from_backup("bad.dump", create_snapshot=True) is False

    terminate_mock.assert_called_once_with()
    restore_mock.assert_called_once_with("good.dump", "good.dump", 1, 3)


def test_restore_from_backup_returns_false_after_retries(backup_system):
    backup_system.paths = {"retry.dump": "retry.dump"}
    restore_mock = MagicMock(side_effect=[False, False, False])

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(backup_system, "_prepare_restore", MagicMock(return_value=True))
        monkeypatch.setattr(backup_system, "_terminate_restore_connections", MagicMock())
        monkeypatch.setattr(backup_system, "_restore_attempt", restore_mock)
        assert backup_system.restore_from_backup("retry.dump", create_snapshot=True) is False

    assert restore_mock.call_count == 3
