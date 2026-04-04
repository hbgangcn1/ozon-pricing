import logging

from db._proxy import _db

logger = logging.getLogger(__name__)


def get_plans(active_only=False, include_free=True):
    """获取所有套餐列表"""
    with _db.get_db_connection() as (_, c):
        try:
            query = "SELECT * FROM plans WHERE 1=1"
            params = []

            if active_only:
                query += " AND is_active = 1"
            if not include_free:
                query += " AND plan_code != 'free'"

            query += " ORDER BY sort_order"
            c.execute(query, params)
            columns = [col[0] for col in c.description]
            rows = c.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.warning("获取套餐列表失败: %s", e)
            return []


def get_plan_by_code(plan_code: str):
    """根据套餐代码获取套餐详情"""
    with _db.get_db_connection() as (conn, c):
        try:
            sql = _db._safe_adapt_sql("SELECT * FROM plans WHERE plan_code = ?", conn)
            c.execute(sql, (plan_code,))
            row = c.fetchone()
            if row:
                columns = [col[0] for col in c.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            logger.warning("获取套餐详情失败: %s", e)
            return None


def get_plan_by_id(plan_id: int):
    """根据ID获取套餐详情"""
    with _db.get_db_connection() as (conn, c):
        try:
            sql = _db._safe_adapt_sql("SELECT * FROM plans WHERE id = ?", conn)
            c.execute(sql, (plan_id,))
            row = c.fetchone()
            if row:
                columns = [col[0] for col in c.description]
                return dict(zip(columns, row))
            return None
        except Exception as e:
            logger.warning("获取套餐详情失败: %s", e)
            return None


def create_plan(
    plan_code: str,
    plan_name: str,
    display_price_month: float,
    display_price_year: float,
    actual_price_month: float,
    actual_price_year: float,
    test_price_month: float = 0.0,
    test_price_year: float = 0.0,
    calc_limit: int = -1,
    logistics_limit: int = 1,
    description: str = "",
    features: str = "",
    is_active: int = 1,
    sort_order: int = 0,
):
    """创建新套餐"""
    with _db.get_db_connection() as (conn, c):
        try:
            existing = c.execute(
                "SELECT id FROM plans WHERE plan_code = ?", (plan_code,)
            ).fetchone()
            if existing:
                print(f"套餐代码 {plan_code} 已存在")
                return False

            c.execute(
                "INSERT INTO plans ("
                "plan_code, plan_name,"
                " display_price_month, display_price_year,"
                " actual_price_month, actual_price_year,"
                " test_price_month, test_price_year,"
                " calc_limit, logistics_limit,"
                " description, features,"
                " is_active, sort_order"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    plan_code,
                    plan_name,
                    display_price_month,
                    display_price_year,
                    actual_price_month,
                    actual_price_year,
                    test_price_month,
                    test_price_year,
                    calc_limit,
                    logistics_limit,
                    description,
                    features,
                    is_active,
                    sort_order,
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.warning("创建套餐失败: %s", e)
            return False


def update_plan(plan_id: int, **kwargs):
    """更新套餐信息"""
    with _db.get_db_connection() as (conn, c):
        try:
            allowed_fields = [
                "plan_name",
                "display_price_month",
                "display_price_year",
                "actual_price_month",
                "actual_price_year",
                "test_price_month",
                "test_price_year",
                "calc_limit",
                "logistics_limit",
                "description",
                "features",
                "is_active",
                "sort_order",
            ]

            updates = []
            values = []
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = ?")
                    values.append(value)

            if not updates:
                return False

            if _db._is_postgresql_connection(conn):
                updates.append("updated_at = extract(epoch from now())")
            else:
                updates.append("updated_at = strftime('%s', 'now')")

            placeholder = _db.get_placeholder()
            query = _db.adapt_sql(
                f"UPDATE plans SET {', '.join(updates)} WHERE id = {placeholder}"
            )
            values.append(plan_id)
            c.execute(query, values)
            conn.commit()
            return c.rowcount > 0
        except Exception as e:
            logger.warning("更新套餐失败: %s", e)
            return False


def delete_plan(plan_id: int):
    """删除套餐"""
    with _db.get_db_connection() as (conn, c):
        try:
            plan = c.execute(
                "SELECT plan_code FROM plans WHERE id = ?", (plan_id,)
            ).fetchone()
            if plan and plan[0] == "free":
                print("不允许删除免费版套餐")
                return False

            sql = _db._safe_adapt_sql("DELETE FROM plans WHERE id = ?", conn)
            c.execute(sql, (plan_id,))
            conn.commit()
            return c.rowcount > 0
        except Exception as e:
            logger.warning("删除套餐失败: %s", e)
            return False


def toggle_plan_active(plan_id: int):
    """切换套餐上下架状态"""
    with _db.get_db_connection() as (conn, c):
        try:
            c.execute(
                "UPDATE plans"
                " SET is_active = 1 - is_active,"
                " updated_at = strftime('%s', 'now')"
                " WHERE id = ?",
                (plan_id,),
            )
            conn.commit()
            return c.rowcount > 0
        except Exception as e:
            logger.warning("切换套餐状态失败: %s", e)
            return False


def get_plan_price(plan_code: str, duration: str, use_test_price: bool = False):
    """获取套餐价格（根据用户角色）"""
    plan = _db.get_plan_by_code(plan_code)
    if not plan:
        return 0

    if use_test_price:
        if duration == "year":
            return plan["test_price_year"]
        return plan["test_price_month"]
    else:
        if duration == "year":
            return plan["actual_price_year"]
        return plan["actual_price_month"]
