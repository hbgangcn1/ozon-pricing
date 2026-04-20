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
from psycopg2 import sql

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

    with psycopg2.connect(**DB_CONFIG) as conn:
        c = conn.cursor()

        c.execute(
            sql.SQL("SELECT COUNT(*) FROM {} WHERE {}").format(
                sql.Identifier("users"),
                sql.SQL(CONDITION),
            )
        )
        count = c.fetchone()[0]
        print(f"Found {count} test user(s) to purge")

        if count == 0:
            print("Nothing to do.")
            return

        if not args.execute:
            c.execute(
                sql.SQL("SELECT id, username, role, is_test_user FROM {} WHERE {} ORDER BY id LIMIT 20").format(
                    sql.Identifier("users"),
                    sql.SQL(CONDITION),
                )
            )
            print("\nSample (first 20):")
            for row in c.fetchall():
                print(f"  id={row[0]}, user={row[1]}, role={row[2]}, is_test={row[3]}")
            remaining = count - min(count, 20)
            if remaining > 0:
                print(f"  ... and {remaining} more")
            print("\nDry-run mode. Use --execute to delete.")
            return

        id_sub = sql.SQL("SELECT id FROM {} WHERE {}").format(
            sql.Identifier("users"),
            sql.SQL(CONDITION),
        )
        name_sub = sql.SQL("SELECT username FROM {} WHERE {}").format(
            sql.Identifier("users"),
            sql.SQL(CONDITION),
        )

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
                c.execute(
                    sql.SQL("DELETE FROM {} WHERE user_id IN ({})").format(
                        sql.Identifier(table),
                        id_sub,
                    )
                )
                if c.rowcount > 0:
                    print(f"  {table}: {c.rowcount} rows deleted")
            except Exception as e:
                conn.rollback()
                print(f"  {table}: skipped ({e})")

        for table in ["login_attempts", "user_lockouts"]:
            try:
                c.execute(
                    sql.SQL("DELETE FROM {} WHERE identifier IN ({})").format(
                        sql.Identifier(table),
                        name_sub,
                    )
                )
                if c.rowcount > 0:
                    print(f"  {table}: {c.rowcount} rows deleted")
            except Exception as e:
                conn.rollback()
                print(f"  {table}: skipped ({e})")

        try:
            c.execute(
                sql.SQL("DELETE FROM {} WHERE admin_id IN ({}) OR target_user_id IN ({})").format(
                    sql.Identifier("admin_action_log"),
                    id_sub,
                    id_sub,
                )
            )
            if c.rowcount > 0:
                print(f"  admin_action_log: {c.rowcount} rows deleted")
        except Exception as e:
            conn.rollback()
            print(f"  admin_action_log: skipped ({e})")

        c.execute(
            sql.SQL("DELETE FROM {} WHERE {}").format(
                sql.Identifier("users"),
                sql.SQL(CONDITION),
            )
        )
        deleted = c.rowcount
        conn.commit()
        c.close()
        print(f"\nDeleted {deleted} test user(s).")

        c.execute(
            sql.SQL("SELECT COUNT(*) FROM {} WHERE {}").format(
                sql.Identifier("users"),
                sql.SQL(CONDITION),
            )
        )
        remaining = c.fetchone()[0]
        print(f"Remaining test users: {remaining}")

        c.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier("users")))
        total = c.fetchone()[0]
        print(f"Total users in database: {total}")

    if remaining > 0:
        print("WARNING: Some test users were not deleted!")
        sys.exit(1)


if __name__ == "__main__":
    main()
