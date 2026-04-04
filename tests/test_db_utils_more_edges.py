import time

from db_utils import (
    get_db_connection,
    add_product,
    update_product,
    delete_product,
    get_product_by_id,
)


def test_product_crud_with_user_isolation():
    # 插入两个用户，分别操作产品，验证 user_id 隔离
    with get_db_connection() as (conn, c):
        from db_adapter import adapt_sql
        sql = adapt_sql(
            "INSERT INTO users(username, password, role, is_test_user) VALUES(?,?,?,?)"
        )
        c.execute(sql, (f"u_iso_a_{int(time.time()*1000)}", "p", "user", 1))
        c.execute(sql, (f"u_iso_b_{int(time.time()*1000)}", "p", "user", 1))
        conn.commit()
        sql = adapt_sql(
            "SELECT id FROM users WHERE username LIKE ? "
            "ORDER BY id DESC LIMIT 1"
        )
        c.execute(sql, ('u_iso_a_%',))
        a = c.fetchone()[0]
        c.execute(sql, ('u_iso_b_%',))
        b = c.fetchone()[0]

    pid = add_product({
        "user_id": a,
        "name": "P1",
        "russian_name": "R1",
        "category": "C",
        "model": "M",
        "unit_price": 1.0,
        "weight_g": 10,
        "length_cm": 1,
        "width_cm": 1,
        "height_cm": 1,
        "is_cylinder": 0,
        "cylinder_diameter": 0.0,
        "cylinder_length": 0.0,
        "has_battery": 0,
        "battery_capacity_wh": 0.0,
        "battery_capacity_mah": 0,
        "battery_voltage": 0.0,
        "has_msds": 0,
        "has_liquid": 0,
        "shipping_fee": 0.0,
        "labeling_fee": 0.0,
        "promotion_discount": 0.0,
        "promotion_cost_rate": 0.0,
        "target_profit_margin": 0.2,
        "commission_rate": 0.0,
        "withdrawal_fee_rate": 0.0,
        "payment_processing_fee": 0.0,
    })
    assert isinstance(pid, int)

    # 另一个用户读取应返回 None
    assert get_product_by_id(pid, b) is None
    # 原用户可以读取
    row = get_product_by_id(pid, a)
    assert row and row["name"] == "P1"

    # 更新与删除
    assert update_product(pid, a, {"name": "P1X"}) is True
    assert delete_product(pid, a) is True
    # 再次读取为 None
    assert get_product_by_id(pid, a) is None

