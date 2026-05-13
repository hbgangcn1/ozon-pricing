"""Production schema integrity guard.

Validates critical DB invariants that ``alembic check`` cannot catch:
CHECK constraints declared only in migration DDL, NOT NULL constraints on
business-critical columns, and core foreign keys.
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

import psycopg2  # type: ignore[import-untyped]

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

CheckMap = Dict[str, Dict[str, Set[str]]]

EXPECTED_CHECK_VALUES: CheckMap = {
    "logistics": {
        "logistics_volume_mode_check": {
            "none",
            "max_actual_vs_volume",
            "longest_side",
            "sum_of_sides",
        },
    },
    "trial_overflow_window": {
        "ck_trial_overflow_window_close_reason": {
            "''",
            "expired",
            "upgraded",
            "reselected",
        },
    },
}

EXPECTED_NOT_NULL: Dict[str, Set[str]] = {
    "users": {"id", "trial_used", "trial_started_at", "trial_expires_at", "updated_at"},
    "products": {"id", "user_id", "updated_at"},
    "logistics": {"id", "user_id", "disabled_by_overflow", "last_used_at", "updated_at"},
    "orders": {"id", "user_id", "order_number", "created_at"},
    "payment_orders": {"id", "order_id", "user_id", "amount", "description", "created_at"},
    "wechat_notify_audit_logs": {
        "id",
        "signature_verified",
        "raw_body",
        "response_code",
        "response_message",
        "created_at",
    },
}

EXPECTED_FOREIGN_KEYS: Set[Tuple[str, str, str, str]] = {
    ("password_reset_tokens", "user_id", "users", "id"),
    ("trial_overflow_window", "user_id", "users", "id"),
}

EXPECTED_INDEXES: Dict[str, Set[str]] = {
    "logistics": {"ix_logistics_user_id_id_desc"},
    "payment_orders": {"ix_payment_orders_user_status_created_at_desc"},
    "active_sessions": {"ix_active_sessions_user_active_last_activity"},
    "wechat_notify_audit_logs": {
        "ix_wechat_notify_audit_logs_bad_sig_created_at_desc",
        "ix_wechat_notify_audit_logs_created_at_transaction_id",
    },
}


def _connect():
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def _string_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _kw_string(node: ast.Call, name: str) -> str | None:
    for kw in node.keywords:
        if kw.arg == name:
            return _string_value(kw.value)
    return None


def _extract_values(sql_text: str) -> Set[str]:
    values = set(re.findall(r"'([^']*)'", sql_text))
    values.discard("")
    if "''" in sql_text:
        values.add("''")
    return values


def _merge_check(result: CheckMap, table: str, name: str, values: Set[str]) -> None:
    if not table or not name or not values:
        return
    result.setdefault(table, {}).setdefault(name, set()).update(values)


def _scan_call_for_check(call: ast.Call, result: CheckMap) -> None:
    func = call.func
    attr = getattr(func, "attr", None)
    if attr == "create_check_constraint" and len(call.args) >= 3:
        name = _string_value(call.args[0])
        table = _string_value(call.args[1])
        condition = _string_value(call.args[2])
        if name and table and condition:
            _merge_check(result, table, name, _extract_values(condition))
    if attr == "CheckConstraint" and call.args:
        condition = _string_value(call.args[0])
        name = _kw_string(call, "name")
        if condition and name:
            table = getattr(call, "_parent_table", None)
            if table:
                _merge_check(result, table, name, _extract_values(condition))


def _scan_create_table(node: ast.Call, result: CheckMap) -> None:
    if getattr(node.func, "attr", None) != "create_table" or not node.args:
        return
    table = _string_value(node.args[0])
    if not table:
        return
    for arg in node.args[1:]:
        if isinstance(arg, ast.Call) and getattr(arg.func, "attr", None) == "CheckConstraint":
            setattr(arg, "_parent_table", table)
            _scan_call_for_check(arg, result)


def scan_alembic_checks(versions_dir: Path | None = None) -> CheckMap:
    base = versions_dir or Path(__file__).resolve().parent.parent / "alembic" / "versions"
    result: CheckMap = {}
    for path in sorted(base.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                _scan_create_table(node, result)
                _scan_call_for_check(node, result)
    return result


def expected_checks() -> CheckMap:
    merged = scan_alembic_checks()
    for table, constraints in EXPECTED_CHECK_VALUES.items():
        for name, values in constraints.items():
            scanned = merged.get(table, {}).get(name)
            if scanned and scanned != values:
                print(f"[WARN] hard-coded CHECK overrides scanned {table}.{name}")
            merged.setdefault(table, {})[name] = set(values)
    return merged


def _fetch_constraint_def(conn, table: str, name: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = %s AND c.conname = %s
            """,
            (table, name),
        )
        row = cur.fetchone()
        return row[0] if row else None


def _fetch_not_null_columns(conn, table: str) -> Set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND is_nullable = 'NO'
            """,
            (table,),
        )
        return {row[0] for row in cur.fetchall()}


def _fetch_foreign_keys(conn) -> Set[Tuple[str, str, str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT tc.table_name, kcu.column_name,
                   ccu.table_name AS foreign_table_name,
                   ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = current_schema()
            """
        )
        return {tuple(row) for row in cur.fetchall()}


def _fetch_indexes(conn, table: str) -> Set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = %s
            """,
            (table,),
        )
        return {row[0] for row in cur.fetchall()}


def _check_checks(conn, failures: List[str]) -> None:
    for table, constraints in expected_checks().items():
        for name, expected in constraints.items():
            actual_def = _fetch_constraint_def(conn, table, name)
            if actual_def is None:
                failures.append(f"[MISSING] {table}.{name} not found in database")
                continue
            missing = sorted(v for v in expected if v not in actual_def)
            if missing:
                failures.append(
                    f"[DRIFT] {table}.{name} missing values: {missing}\n"
                    f"         actual: {actual_def}"
                )
            else:
                print(f"[OK] {table}.{name}")


def _check_not_null(conn, failures: List[str]) -> None:
    for table, expected in EXPECTED_NOT_NULL.items():
        actual = _fetch_not_null_columns(conn, table)
        missing = sorted(expected - actual)
        if missing:
            failures.append(f"[DRIFT] {table} nullable critical columns: {missing}")
        else:
            print(f"[OK] {table} NOT NULL critical columns")


def _check_foreign_keys(conn, failures: List[str]) -> None:
    actual = _fetch_foreign_keys(conn)
    for fk in sorted(EXPECTED_FOREIGN_KEYS):
        if fk not in actual:
            failures.append(f"[MISSING] FK {fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]}")
        else:
            print(f"[OK] FK {fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]}")


def _check_indexes(conn, failures: List[str]) -> None:
    for table, expected in EXPECTED_INDEXES.items():
        actual = _fetch_indexes(conn, table)
        missing = sorted(expected - actual)
        if missing:
            failures.append(f"[MISSING] {table} indexes: {missing}")
        else:
            print(f"[OK] {table} hot path indexes")


def run_checks(conn) -> List[str]:
    failures: List[str] = []
    _check_checks(conn, failures)
    _check_not_null(conn, failures)
    _check_foreign_keys(conn, failures)
    _check_indexes(conn, failures)
    return failures


def _print_failures(failures: Sequence[str]) -> None:
    print("\nSCHEMA INTEGRITY CHECK FAILED:")
    for failure in failures:
        print(f"  - {failure}")
    print(
        "\nLikely cause: alembic_version stamped past a migration whose DDL "
        "never executed, or production schema drifted from core invariants."
    )


def main() -> int:
    conn = _connect()
    try:
        failures = run_checks(conn)
    finally:
        conn.close()
    if failures:
        _print_failures(failures)
        return 1
    print("\nSchema integrity OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
