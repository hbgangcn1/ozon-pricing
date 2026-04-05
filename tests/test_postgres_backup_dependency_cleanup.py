import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import postgres_backup_service  # noqa: E402  pylint: disable=wrong-import-position


class DummyCursor:
    def __init__(self, fetchall_data):
        self.fetchall_data = fetchall_data
        self.commands = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, _params=None):  # noqa: ARG001
        self.commands.append(sql.strip())

    def fetchall(self):
        return self.fetchall_data


class DummyConnection:
    def __init__(self, fetchall_data):
        self.fetchall_data = fetchall_data
        self.closed = False
        self.autocommit = False
        self.cursor_obj = DummyCursor(fetchall_data)

    def cursor(self):
        return self.cursor_obj

    def close(self):
        self.closed = True


def test_drop_all_foreign_keys_executes_drop_statements():
    backup_system = postgres_backup_service.PostgresBackupSystem()
    postgres_backup_service.logger = MagicMock()

    fk_rows = [
        ('public', 'orders', 'orders_user_id_fkey'),
        ('public', 'payments', 'payments_order_id_fkey'),
    ]
    dummy_conn = DummyConnection(fk_rows)

    with patch('postgres_backup_service.psycopg2.connect',
               return_value=dummy_conn):
        backup_system._drop_all_foreign_keys()  # pyright: ignore[reportPrivateUsage]

    executed = "\n".join(dummy_conn.cursor_obj.commands)
    assert "DROP CONSTRAINT IF EXISTS orders_user_id_fkey" in executed
    assert "DROP CONSTRAINT IF EXISTS payments_order_id_fkey" in executed
    postgres_backup_service.logger.info.assert_any_call(
        "✅ 已删除 2 个外键约束"
    )


def test_drop_sequence_dependencies_executes_alter_column():
    backup_system = postgres_backup_service.PostgresBackupSystem()
    postgres_backup_service.logger = MagicMock()

    seq_rows = [
        ('public', 'users', 'id', "nextval('users_id_seq'::regclass)")
    ]
    dummy_conn = DummyConnection(seq_rows)

    with patch('postgres_backup_service.psycopg2.connect',
               return_value=dummy_conn):
        backup_system._drop_sequence_dependencies()  # pyright: ignore[reportPrivateUsage]

    executed = "\n".join(dummy_conn.cursor_obj.commands)
    assert "ALTER COLUMN id DROP DEFAULT" in executed
    postgres_backup_service.logger.info.assert_any_call(
        "✅ 已删除 1 个序列依赖"
    )

