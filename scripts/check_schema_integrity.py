"""Production schema integrity guard.

Validates critical DB invariants that ``alembic check`` cannot catch
(e.g. CHECK constraints declared only in migration DDL, not in models).

Run after ``alembic upgrade head`` in deploy pipeline. Non-zero exit
aborts the deploy.

Add new invariants to ``EXPECTED_CHECK_VALUES`` whenever a migration
introduces or extends a CHECK constraint.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Set

import psycopg2  # type: ignore[import-untyped]

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Expected CHECK constraint allowed-value sets.
# Format: {table: {constraint_name: {expected_value, ...}}}
# Script asserts the live constraint definition CONTAINS every expected value.
# ---------------------------------------------------------------------------
EXPECTED_CHECK_VALUES: Dict[str, Dict[str, Set[str]]] = {
    "logistics": {
        "logistics_volume_mode_check": {
            "none",
            "max_actual_vs_volume",
            "longest_side",
            "sum_of_sides",
        },
    },
}


def _connect():
    url = os.environ.get("DATABASE_URL")
    if url:
        # psycopg2 wants postgresql:// not postgresql+asyncpg://
        return psycopg2.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


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


def main() -> int:
    failures: list[str] = []
    conn = _connect()
    try:
        for table, constraints in EXPECTED_CHECK_VALUES.items():
            for name, expected in constraints.items():
                actual_def = _fetch_constraint_def(conn, table, name)
                if actual_def is None:
                    failures.append(
                        f"[MISSING] {table}.{name} not found in database"
                    )
                    continue
                missing = sorted(v for v in expected if v not in actual_def)
                if missing:
                    failures.append(
                        f"[DRIFT] {table}.{name} missing values: "
                        f"{missing}\n         actual: {actual_def}"
                    )
                else:
                    print(f"[OK] {table}.{name}")
    finally:
        conn.close()

    if failures:
        print("\nSCHEMA INTEGRITY CHECK FAILED:")
        for f in failures:
            print(f"  - {f}")
        print(
            "\nLikely cause: alembic_version stamped past a migration whose "
            "DDL never executed (e.g. restored from dump + alembic stamp). "
            "Manually apply the missing DDL or restore from backup."
        )
        return 1

    print("\nSchema integrity OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
