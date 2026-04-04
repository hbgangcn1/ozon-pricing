from db_utils import init_db, get_db_connection


def test_init_db_idempotent_and_upgrades_noop():
    # 第一次初始化
    init_db()
    with get_db_connection() as (conn, c):
        # 基础表应存在
        for t in ("users", "products", "logistics"):
            c.execute(f"SELECT COUNT(*) FROM {t}")
            assert c.fetchone() is not None

    # 第二次初始化不应抛错且无破坏性
    init_db()
    with get_db_connection() as (conn, c):
        # 重复调用后字段仍可查询
        from db_utils import (
            _is_postgresql_connection,  # pyright: ignore[reportPrivateUsage]
        )
        if _is_postgresql_connection(conn):
            # PostgreSQL使用information_schema
            c.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'products'
                ORDER BY ordinal_position
            """)
        else:
            # SQLite使用PRAGMA
            c.execute("PRAGMA table_info(products)")
        cols = [col[0] if _is_postgresql_connection(conn) else col[1] 
                for col in c.fetchall()]
        for need in (
            "promotion_discount", "promotion_cost_rate",
            "target_profit_margin", "commission_rate", "withdrawal_fee_rate",
            "payment_processing_fee", "cylinder_length",
        ):
            assert need in cols

