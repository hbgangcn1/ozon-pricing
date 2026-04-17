#!/usr/bin/env python3
"""
One-time purge of accumulated test users from the database.

Usage:
    python scripts/purge_test_users.py           # dry-run (preview)
    python scripts/purge_test_users.py --execute  # actually delete
"""

import argparse
import os
import sys

import psycopg2

DB_CONFIG = {
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname": os.environ.get("POSTGRES_DB", "logistics"),
    "user": os.environ.get("POSTGRES_USER", "postgres"),
    "password": os.environ.get("POSTGRES_PASSWORD", ""),
}

CONDITION = (
    "(is_test_user = 1 OR username LIKE 'test_%%' OR username LIKE 'e2e%%') AND id != 1"
)


def main():
    if not DB_CONFIG["password"]:
        print("ERROR: POSTGRES_PASSWORD environment variable must be set")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Purge accumulated test users from database",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete (default is dry-run preview)",
    )
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)
    c = conn.cursor()

    c.execute(f"SELECT COUNT(*) FROM users WHERE {CONDITION}")
    count = c.fetchone()[0]
    print(f"Found {count} test user(s) to purge")

    if count == 0:
        print("Nothing to do.")
        conn.close()
        return

    if not args.execute:
        c.execute(
            "SELECT id, username, role, is_test_user"
            f" FROM users WHERE {CONDITION}"
            " ORDER BY id LIMIT 20"
        )
        print("\nSample (first 20):")
        for row in c.fetchall():
            print(f"  id={row[0]}, user={row[1]}, role={row[2]}, is_test={row[3]}")
        remaining = count - min(count, 20)
        if remaining > 0:
            print(f"  ... and {remaining} more")
        print("\nDry-run mode. Use --execute to delete.")
        conn.close()
        return

    id_sub = f"SELECT id FROM users WHERE {CONDITION}"
    name_sub = f"SELECT username FROM users WHERE {CONDITION}"

    for table in [
        "products",
        "logistics",
        "payment_orders",
        "active_sessions",
        "subscription_upgrade_history",
        "user_login_log",
        "user_behavior_log",
    ]:
        try:
            c.execute(f"DELETE FROM {table} WHERE user_id IN ({id_sub})")
            if c.rowcount > 0:
                print(f"  {table}: {c.rowcount} rows deleted")
        except Exception as e:
            conn.rollback()
            print(f"  {table}: skipped ({e})")

    for table in ["login_attempts", "user_lockouts"]:
        try:
            c.execute(f"DELETE FROM {table} WHERE identifier IN ({name_sub})")
            if c.rowcount > 0:
                print(f"  {table}: {c.rowcount} rows deleted")
        except Exception as e:
            conn.rollback()
            print(f"  {table}: skipped ({e})")

    try:
        c.execute(
            "DELETE FROM admin_action_log"
            f" WHERE admin_id IN ({id_sub})"
            f" OR target_user_id IN ({id_sub})"
        )
        if c.rowcount > 0:
            print(f"  admin_action_log: {c.rowcount} rows deleted")
    except Exception as e:
        conn.rollback()
        print(f"  admin_action_log: skipped ({e})")

    c.execute(f"DELETE FROM users WHERE {CONDITION}")
    deleted = c.rowcount
    conn.commit()
    print(f"\nDeleted {deleted} test user(s).")

    c.execute(f"SELECT COUNT(*) FROM users WHERE {CONDITION}")
    remaining = c.fetchone()[0]
    print(f"Remaining test users: {remaining}")

    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    print(f"Total users in database: {total}")

    c.close()
    conn.close()

    if remaining > 0:
        print("WARNING: Some test users were not deleted!")
        sys.exit(1)


if __name__ == "__main__":
    main()
