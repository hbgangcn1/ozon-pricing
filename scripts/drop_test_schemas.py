"""One-shot dev utility: drop residual test_* schemas left over from xdist crashes.

Usage: python scripts/drop_test_schemas.py
"""
from __future__ import annotations

import os
import sys

import psycopg2
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if url:
        print(f"Using URL {url[:60]}...")
        conn = psycopg2.connect(url)
    else:
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = int(os.environ.get("POSTGRES_PORT", "5432"))
        dbname = os.environ.get("POSTGRES_DB", "logistics")
        user = os.environ.get("POSTGRES_USER", "logistics_user")
        pw = os.environ.get("POSTGRES_PASSWORD", "")
        print(f"Using {user}@{host}:{port}/{dbname}")
        conn = psycopg2.connect(
            host=host, port=port, dbname=dbname, user=user, password=pw
        )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "SELECT nspname FROM pg_namespace "
        "WHERE nspname LIKE 'test\\_%' ESCAPE '\\' "
        "ORDER BY nspname"
    )
    rows = [r[0] for r in cur.fetchall()]
    print(f"Found {len(rows)} test schemas: {rows}")
    for s in rows:
        try:
            cur.execute(f'DROP SCHEMA IF EXISTS "{s}" CASCADE')
            print(f"  dropped {s}")
        except psycopg2.errors.InsufficientPrivilege:
            conn.rollback()
            print(f"  skipped {s} (not owner)")
    cur.close()
    conn.close()
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
