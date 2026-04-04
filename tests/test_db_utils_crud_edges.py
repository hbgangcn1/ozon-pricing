import pytest
import time

from db_utils import (
    get_db_connection,
    add_product,
    update_product,
    batch_update_pricing_params,
    get_product_by_id,
)


def test_update_product_empty_updates_returns_false():
    """测试空更新字典返回False"""
    try:
        with get_db_connection() as (conn, c):
            # 调试信息：记录连接状态
            conn_status = "未知"
            try:
                if hasattr(conn, 'closed'):
                    conn_status = "打开" if conn.closed == 0 else "关闭"  # type: ignore[attr-defined]
            except (AttributeError, TypeError):
                pass

            from db_utils import (
                _safe_adapt_sql,  # pyright: ignore[reportPrivateUsage]
                get_placeholder,
            )
            u1 = f"crud_u1_{int(time.time()*1000)}"
            placeholder = get_placeholder()
            sql_raw = (
                f"INSERT INTO users(username,password,role,is_test_user) "
                f"VALUES({placeholder},{placeholder},{placeholder},"
                f"{placeholder})"
            )
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (u1, "p", "user", 1))
            
            # 调试信息：检查连接状态
            try:
                if hasattr(conn, 'closed') and conn.closed != 0:  # type: ignore[attr-defined]
                    raise RuntimeError(
                        f"连接在执行commit前已关闭。"
                        f"连接状态: {conn_status}"
                    )
                conn.commit()
            except Exception as commit_err:
                # 记录提交错误但继续执行
                import sys
                print(
                    f"警告：提交用户创建时出错: {type(commit_err).__name__}: "
                    f"{commit_err}",
                    file=sys.stderr
                )
                raise
            
            sql_raw = f"SELECT id FROM users WHERE username={placeholder}"
            sql = _safe_adapt_sql(sql_raw, conn)
            c.execute(sql, (u1,))
            result = c.fetchone()
            if result is None:
                raise ValueError(f"未找到用户: {u1}")
            uid = result[0]

        # 在连接上下文外创建产品
        pid = add_product({
            "user_id": uid,
            "name": "P",
            "russian_name": "R",
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
        
        # 调试信息：验证产品ID
        assert pid is not None, f"产品创建失败，返回None"
        
        result = update_product(pid, uid, {})
        assert result is False, (
            f"空更新字典应该返回False，但返回了: {result}. "
            f"产品ID: {pid}, 用户ID: {uid}"
        )
    except Exception as e:
        # 添加详细的错误信息
        import traceback
        error_details = traceback.format_exc()
        raise AssertionError(
            f"测试失败，异常类型: {type(e).__name__}, "
            f"异常消息: {str(e)}\n"
            f"详细堆栈:\n{error_details}"
        ) from e


def test_batch_update_pricing_params_empty_inputs():
    with get_db_connection() as (conn, c):
        from db_utils import (
            _safe_adapt_sql,  # pyright: ignore[reportPrivateUsage]
            get_placeholder,
        )
        u2 = f"crud_u2_{int(time.time()*1000)}"
        placeholder = get_placeholder()
        sql_raw = f"INSERT INTO users(username,password,role,is_test_user) VALUES({placeholder},{placeholder},{placeholder},{placeholder})"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (u2, "p", "user", 1))
        conn.commit()
        sql_raw = f"SELECT id FROM users WHERE username={placeholder}"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (u2,))
        uid = c.fetchone()[0]

    # 空 IDs
    assert batch_update_pricing_params(
        [], uid, {"promotion_discount": 0.1}
    ) == 0
    # 空字段
    assert batch_update_pricing_params([1, 2], uid, {}) == 0


def test_get_product_by_id_requires_user_id():
    with pytest.raises(ValueError):
        get_product_by_id(1, None)

