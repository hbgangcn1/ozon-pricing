import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import postgres_backup_service  # noqa: E402  pylint: disable=wrong-import-position
import postgres_backup_service_db  # noqa: E402  pylint: disable=wrong-import-position

from psycopg2 import sql  # noqa: E402


def _build_mock_conn(fetchall_data):
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = fetchall_data
    mock_cur.__enter__ = MagicMock(return_value=mock_cur)
    mock_cur.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn, mock_cur


def _composed_repr_contains(composed_obj, *needles):
    text = repr(composed_obj)
    return all(needle in text for needle in needles)


def test_drop_all_foreign_keys_executes_drop_statements():
    backup_system = postgres_backup_service.PostgresBackupSystem()

    fk_rows = [
        ("public", "orders", "orders_user_id_fkey"),
        ("public", "payments", "payments_order_id_fkey"),
    ]
    mock_conn, mock_cur = _build_mock_conn(fk_rows)

    with patch(
        "postgres_backup_service_db.psycopg2.connect",
        return_value=mock_conn,
    ):
        with patch("postgres_backup_service_db.logger") as mock_logger:
            backup_system._drop_all_foreign_keys()  # pyright: ignore[reportPrivateUsage]

    execute_calls = mock_cur.execute.call_args_list
    alter_calls = [c for c in execute_calls if isinstance(c[0][0], sql.Composable)]
    assert len(alter_calls) == 2

    assert _composed_repr_contains(
        alter_calls[0][0][0],
        "DROP CONSTRAINT IF EXISTS",
        "orders_user_id_fkey",
    )
    assert _composed_repr_contains(
        alter_calls[1][0][0],
        "DROP CONSTRAINT IF EXISTS",
        "payments_order_id_fkey",
    )

    mock_logger.info.assert_any_call("✅ 已删除 {} 个外键约束", 2)


def test_drop_sequence_dependencies_executes_alter_column():
    backup_system = postgres_backup_service.PostgresBackupSystem()

    seq_rows = [("public", "users", "id", "nextval('users_id_seq'::regclass)")]
    mock_conn, mock_cur = _build_mock_conn(seq_rows)

    with patch(
        "postgres_backup_service_db.psycopg2.connect",
        return_value=mock_conn,
    ):
        with patch("postgres_backup_service_db.logger") as mock_logger:
            backup_system._drop_sequence_dependencies()  # pyright: ignore[reportPrivateUsage]

    execute_calls = mock_cur.execute.call_args_list
    alter_calls = [c for c in execute_calls if isinstance(c[0][0], sql.Composable)]
    assert len(alter_calls) == 1

    assert _composed_repr_contains(
        alter_calls[0][0][0],
        "ALTER COLUMN",
        "DROP DEFAULT",
    )

    mock_logger.info.assert_any_call("✅ 已删除 {} 个序列依赖", 1)
