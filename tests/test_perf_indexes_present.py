from sqlalchemy import inspect, text

from database import engine


EXPECTED_INDEXES = {
    "logistics": {"ix_logistics_user_id_id_desc"},
    "payment_orders": {"ix_payment_orders_user_status_created_at_desc"},
    "active_sessions": {"ix_active_sessions_user_active_last_activity"},
    "wechat_notify_audit_logs": {
        "ix_wechat_notify_audit_logs_bad_sig_created_at_desc",
        "ix_wechat_notify_audit_logs_created_at_transaction_id",
    },
}


async def test_perf_hot_path_indexes_present():
    async with engine.connect() as conn:
        found = await conn.run_sync(_inspect_indexes)

    for table, expected in EXPECTED_INDEXES.items():
        assert expected <= found[table]


async def test_order_id_unique_constraint_covers_out_trade_no_mapping():
    async with engine.connect() as conn:
        is_unique = await conn.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_indexes
                    WHERE schemaname = current_schema()
                      AND tablename = 'payment_orders'
                      AND indexdef ILIKE '%UNIQUE%'
                      AND indexdef ILIKE '%order_id%'
                )
                """
            )
        )

    assert is_unique is True


async def test_requested_missing_legacy_columns_not_introduced():
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND (
                    (table_name = 'products' AND column_name = 'sku') OR
                    (table_name = 'payment_orders' AND column_name = 'out_trade_no') OR
                    (table_name = 'active_sessions' AND column_name = 'expires_at')
                  )
                """
            )
        )
        tables = await conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name IN ('orders', 'logistics_records', 'sessions')
                """
            )
        )

    assert rows.fetchall() == []
    assert tables.fetchall() == []


def _inspect_indexes(sync_conn):
    inspector = inspect(sync_conn)
    return {
        table: {idx["name"] for idx in inspector.get_indexes(table)}
        for table in EXPECTED_INDEXES
    }
