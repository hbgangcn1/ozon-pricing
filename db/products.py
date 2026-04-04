import logging

from db._proxy import _db
from db.helpers import DB_EXCEPTIONS

logger = logging.getLogger(__name__)

_ALLOWED_PRODUCT_FIELDS = {
    "user_id",
    "name",
    "russian_name",
    "category",
    "model",
    "unit_price",
    "weight_g",
    "length_cm",
    "width_cm",
    "height_cm",
    "is_cylinder",
    "cylinder_diameter",
    "cylinder_length",
    "has_battery",
    "battery_capacity_wh",
    "battery_capacity_mah",
    "battery_voltage",
    "has_msds",
    "has_liquid",
    "labeling_fee",
    "shipping_fee",
    "promotion_cost_rate",
    "target_profit_margin",
    "commission_rate",
    "withdrawal_fee_rate",
    "payment_processing_fee",
    "return_rate",
    "vat_rate",
    "is_test_data",
}

_BASE_PRODUCT_FIELDS = [
    "user_id",
    "name",
    "russian_name",
    "category",
    "model",
    "unit_price",
    "weight_g",
    "length_cm",
    "width_cm",
    "height_cm",
    "is_cylinder",
    "cylinder_diameter",
    "cylinder_length",
    "has_battery",
    "battery_capacity_wh",
    "battery_capacity_mah",
    "battery_voltage",
    "has_msds",
    "has_liquid",
    "shipping_fee",
    "labeling_fee",
    "promotion_cost_rate",
    "target_profit_margin",
    "commission_rate",
    "withdrawal_fee_rate",
    "payment_processing_fee",
    "return_rate",
]

_BOOL_FIELDS = {"is_cylinder", "has_battery", "has_msds", "has_liquid"}


def _ensure_is_test_data_column(conn, c):
    """确保is_test_data列存在（向后兼容）"""
    cols = _db._get_table_columns(c, "products")
    if "is_test_data" not in cols:
        try:
            c.execute("ALTER TABLE products ADD COLUMN is_test_data INTEGER DEFAULT 0")
            conn.commit()
        except DB_EXCEPTIONS:
            pass


def _build_product_insert_values(product_data):
    """从product_data构建字段名字符串、占位符字符串和值列表"""
    placeholder = _db.get_placeholder()
    field_names = ",".join(_BASE_PRODUCT_FIELDS) + ",is_test_data"
    placeholders = (
        ",".join([placeholder for _ in _BASE_PRODUCT_FIELDS]) + f",{placeholder}"
    )
    values = []
    for field in _BASE_PRODUCT_FIELDS:
        val = product_data.get(field, 0)
        if field in _BOOL_FIELDS:
            val = 1 if val else 0
        values.append(val)
    values.append(product_data.get("is_test_data", 0))
    return field_names, placeholders, values


def _validate_product_fields(field_names):
    """使用sql_security模块验证字段名"""
    try:
        from sql_security import validate_field_names, SQLSecurityError
    except ImportError:
        from sql_security import validate_field_names, SQLSecurityError  # noqa

    field_list = [f.strip() for f in field_names.split(",")]
    try:
        validate_field_names(field_list, _ALLOWED_PRODUCT_FIELDS)
    except SQLSecurityError as e:
        raise ValueError(f"SQL安全错误: {e}") from e


def add_product(product_data):
    """添加新产品

    Args:
        product_data: 产品数据字典，可包含is_test_data字段
                     - is_test_data=0或未设置：手动创建的产品
                     - is_test_data=1：测试数据
    """
    with _db.get_db_connection() as (conn, c):
        _ensure_is_test_data_column(conn, c)
        field_names, placeholders, values = _build_product_insert_values(product_data)
        _validate_product_fields(field_names)

        sql_raw = (
            f"INSERT INTO products ({field_names}) VALUES ({placeholders}) RETURNING id"
        )
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, values)
        result = c.fetchone()
        conn.commit()
        return result[0] if result else None


def get_all_products_for_user(user_id):
    """获取用户的所有产品"""
    with _db.get_db_connection() as (conn, c):
        sql = _db._safe_adapt_sql("SELECT * FROM products WHERE user_id = ?", conn)
        c.execute(sql, (user_id,))
        products = c.fetchall()
        if _db._is_postgresql_connection(conn):
            columns = [desc[0] for desc in c.description]
        else:
            columns = [col[0] for col in c.description]
        return [dict(zip(columns, product)) for product in products]


def ensure_admin_product_deletion_allowed() -> None:
    """确保不存在阻止删除管理员产品的触发器。"""
    with _db.get_db_connection() as (conn, c):
        try:
            if _db._is_postgresql_connection(conn):
                sql = (
                    "DROP TRIGGER IF EXISTS trg_prevent_delete_admin_products"
                    " ON products"
                )
                c.execute(sql)
            else:
                c.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_admin_products")
            conn.commit()
        except DB_EXCEPTIONS:
            pass


def get_product_by_id(product_id, user_id):
    """根据ID获取产品 - 强制要求用户ID验证"""
    if user_id is None:
        raise ValueError("user_id参数是必需的，以确保数据安全隔离")

    with _db.get_db_connection() as (conn, c):
        sql = "SELECT * FROM products WHERE id = ? AND user_id = ?"
        product = _db._safe_execute_fetchone(c, sql, (product_id, user_id), conn)
        if product:
            columns = [description[0] for description in c.description]
            return dict(zip(columns, product))
        return None


def delete_product(product_id, user_id):
    """删除产品"""
    with _db.get_db_connection() as (conn, c):
        sql = "SELECT is_test_data FROM products WHERE id = ? AND user_id = ?"
        product = _db._safe_execute_fetchone(c, sql, (product_id, user_id), conn)

        if not product:
            return False

        sql = _db._safe_adapt_sql("DELETE FROM products WHERE id = ? AND user_id = ?", conn)
        c.execute(sql, (product_id, user_id))
        conn.commit()
        return c.rowcount > 0


def batch_delete_products(product_ids, user_id):
    """批量删除产品"""
    if not product_ids:
        return 0
    with _db.get_db_connection() as (conn, c):
        try:
            from sql_security import build_in_clause, SQLSecurityError
        except ImportError:
            from sql_security import build_in_clause, SQLSecurityError  # noqa

        try:
            in_clause, validated_ids = build_in_clause(product_ids)
        except SQLSecurityError as e:
            raise ValueError(f"SQL安全错误: {e}") from e

        params = validated_ids + [user_id]
        sql_raw = f"DELETE FROM products WHERE id {in_clause} AND user_id = ?"
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, params)
        conn.commit()
        return c.rowcount


def cleanup_test_products(user_id=None):
    """清理测试产品（is_test_data=1）"""
    try:
        with _db.get_db_connection() as (conn, c):
            cols = _db._get_table_columns(c, "products")
            if "is_test_data" not in cols:
                return 0

            if user_id:
                sql_raw = "DELETE FROM products WHERE is_test_data = 1 AND user_id = ?"
            else:
                sql_raw = "DELETE FROM products WHERE is_test_data = 1"

            sql = _db._safe_adapt_sql(sql_raw, conn)
            if user_id:
                c.execute(sql, (user_id,))
            else:
                c.execute(sql)
            conn.commit()
            return c.rowcount
    except Exception as e:
        logger.warning("清理测试产品时出错: %s", e)
        return 0


def update_product(product_id, user_id, updates):
    """更新产品信息"""
    if not updates:
        return False

    try:
        from sql_security import build_update_set_clause, SQLSecurityError
    except ImportError:
        from sql_security import build_update_set_clause, SQLSecurityError  # noqa

    with _db.get_db_connection() as (conn, c):
        allowed = _ALLOWED_PRODUCT_FIELDS - {"user_id"}
        try:
            set_clause, values = build_update_set_clause(updates, allowed)
        except SQLSecurityError as e:
            raise ValueError(f"SQL安全错误: {e}") from e

        values.extend([product_id, user_id])
        sql_raw = f"UPDATE products SET {set_clause} WHERE id = ? AND user_id = ?"
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, values)
        conn.commit()
        return c.rowcount > 0


def batch_update_pricing_params(product_ids, user_id, pricing_updates):
    """批量更新产品定价参数"""
    if not product_ids or not pricing_updates:
        return 0

    try:
        from sql_security import (
            build_update_set_clause,
            build_in_clause,
            SQLSecurityError,
        )
    except ImportError:
        from sql_security import (  # noqa
            build_update_set_clause,
            build_in_clause,
            SQLSecurityError,
        )

    with _db.get_db_connection() as (conn, c):
        allowed_pricing_fields = {
            "promotion_cost_rate",
            "target_profit_margin",
            "commission_rate",
            "withdrawal_fee_rate",
            "payment_processing_fee",
            "return_rate",
            "vat_rate",
            "unit_price",
            "labeling_fee",
            "shipping_fee",
        }

        try:
            set_clause, values = build_update_set_clause(
                pricing_updates, allowed_pricing_fields
            )
            in_clause, validated_ids = build_in_clause(product_ids)
        except SQLSecurityError as e:
            raise ValueError(f"SQL安全错误: {e}") from e

        values.extend(validated_ids)
        values.append(user_id)
        sql = f"UPDATE products SET {set_clause} WHERE id {in_clause} AND user_id = ?"
        sql = _db._safe_adapt_sql(sql, conn)
        c.execute(sql, values)
        conn.commit()
        return c.rowcount


def _calculate_group_averages(logistics_list):
    """计算物流组的平均值"""
    if not logistics_list:
        return 0, 0, 0

    valid_logistics = [
        log for log in logistics_list if log["min_days"] > 0 and log["max_days"] > 0
    ]

    if not valid_logistics:
        return 0, 0, 0

    min_days_sum = sum(log["min_days"] for log in valid_logistics)
    avg_fastest = min_days_sum / len(valid_logistics)

    max_days_sum = sum(log["max_days"] for log in valid_logistics)
    avg_slowest = max_days_sum / len(valid_logistics)

    avg_times = [(log["min_days"] + log["max_days"]) / 2 for log in valid_logistics]
    avg_overall = sum(avg_times) / len(avg_times)

    return avg_fastest, avg_slowest, avg_overall


def _assign_priority_group(log, avg_fastest, avg_slowest, avg_overall):
    """为单个物流分配优先级组"""
    min_days = log["min_days"]
    max_days = log["max_days"]

    if min_days == 0 and max_days == 0:
        return "E"

    avg_time = (min_days + max_days) / 2
    count_below_avg = 0
    if min_days < avg_fastest:
        count_below_avg += 1
    if max_days < avg_slowest:
        count_below_avg += 1
    if avg_time < avg_overall:
        count_below_avg += 1

    if count_below_avg == 3:
        return "A"
    elif count_below_avg == 2:
        return "B"
    elif count_below_avg == 1:
        return "C"
    else:
        return "D"


def _update_logistics_priority_groups(c, conn, logistics_list, avgs):
    """批量更新物流优先级组"""
    avg_fastest, avg_slowest, avg_overall = avgs
    update_sql_raw = "UPDATE logistics SET priority_group = ? WHERE id = ?"
    update_sql = _db._safe_adapt_sql(update_sql_raw, conn)
    for log in logistics_list:
        group = _assign_priority_group(log, avg_fastest, avg_slowest, avg_overall)
        c.execute(update_sql, (group, log["id"]))


def calculate_and_update_priority_groups(user_id):
    """计算并更新物流优先级分组 - 支持用户隔离"""
    with _db.get_db_connection() as (conn, c):
        sql_raw = "SELECT id, type, min_days, max_days FROM logistics WHERE user_id = ?"
        sql = _db._safe_adapt_sql(sql_raw, conn)
        c.execute(sql, (user_id,))
        logistics_raw = c.fetchall()
        logistics = [
            {
                "id": row[0],
                "type": row[1],
                "min_days": row[2],
                "max_days": row[3],
            }
            for row in logistics_raw
        ]

        land_logistics = [log for log in logistics if log["type"] == "land"]
        air_logistics = [log for log in logistics if log["type"] == "air"]

        land_avgs = _calculate_group_averages(land_logistics)
        air_avgs = _calculate_group_averages(air_logistics)

        _update_logistics_priority_groups(c, conn, land_logistics, land_avgs)
        _update_logistics_priority_groups(c, conn, air_logistics, air_avgs)

        conn.commit()
