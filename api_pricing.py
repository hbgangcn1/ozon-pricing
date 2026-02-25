"""
物流定价系统 REST API
提供商品管理、物流规则管理和定价计算的 HTTP 接口。
通过 X-API-Key 请求头进行身份验证。
"""

import os
from flask import Flask, request, jsonify

from werkzeug.security import check_password_hash

from logic import calculate_pricing
from db_utils import add_product, get_product_by_id, update_product, delete_product, get_db_connection
from exchange_service import get_fallback_exchange_rate, get_fallback_usd_rate

import pandas as pd

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("PRICING_API_KEY", "dev-test-key-12345")
API_USER_ID = int(os.environ.get("API_USER_ID", "1"))

# ---------------------------------------------------------------------------
# CORS – try flask_cors first, fall back to manual headers
# ---------------------------------------------------------------------------
try:
    from flask_cors import CORS
    CORS(app)
    _manual_cors = False
except ImportError:
    _manual_cors = True

if _manual_cors:
    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key, X-User-Id"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        return response

# ---------------------------------------------------------------------------
# Parameter placeholder – handle SQLite (?) vs PostgreSQL (%s)
# ---------------------------------------------------------------------------
def _ph():
    """Return the correct SQL parameter placeholder for the current DB backend."""
    try:
        from db_config import DB_TYPE
        if DB_TYPE == "postgresql":
            return "%s"
    except Exception:
        pass
    return "?"

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def _require_auth():
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    return None


def _get_user_id():
    """优先从 X-User-Id 请求头取用户 ID，否则使用默认 API_USER_ID。"""
    header_val = request.headers.get("X-User-Id")
    if header_val is not None:
        try:
            return int(header_val)
        except (ValueError, TypeError):
            pass
    return API_USER_ID


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    """用户登录，返回 user_id 和 username。"""
    data = request.get_json(silent=True)
    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Missing username or password"}), 400
    username = data["username"]
    password = data["password"]
    try:
        ph = _ph()
        with get_db_connection() as (_, cursor):
            cursor.execute(
                f"SELECT id, username, password_hash FROM users WHERE username = {ph}",
                (username,),
            )
            row = cursor.fetchone()
        if not row:
            return jsonify({"error": "Invalid credentials"}), 401
        if hasattr(row, 'keys'):
            user_id = row["id"]
            stored_hash = row["password_hash"]
        else:
            user_id, _, stored_hash = row[0], row[1], row[2]
        if not check_password_hash(stored_hash, password):
            return jsonify({"error": "Invalid credentials"}), 401
        return jsonify({"user_id": user_id, "username": username})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# Product fields
# ---------------------------------------------------------------------------
PRODUCT_FIELDS = [
    "name", "unit_price", "weight_g", "length_cm", "width_cm", "height_cm",
    "commission_rate", "target_profit_margin", "promotion_cost_rate",
    "withdrawal_fee_rate", "payment_processing_fee", "return_rate", "vat_rate",
    "labeling_fee", "shipping_fee", "is_cylinder", "cylinder_diameter",
    "cylinder_length", "has_battery", "battery_capacity_wh", "battery_capacity_mah",
    "battery_voltage", "has_flammable", "has_msds", "russian_name", "category",
    "model", "promotion_discount",
]

# ---------------------------------------------------------------------------
# Logistics fields
# ---------------------------------------------------------------------------
LOGISTICS_FIELDS = [
    "name", "type", "min_days", "max_days", "price_limit", "price_limit_rub",
    "price_limit_currency", "price_min", "price_min_rub", "price_min_currency",
    "base_fee", "min_weight", "max_weight", "max_sum_of_sides", "max_longest_side",
    "max_second_side", "min_second_side", "min_length", "max_cylinder_sum",
    "min_cylinder_sum", "max_cylinder_length", "min_cylinder_length", "volume_mode",
    "longest_side_threshold", "allow_battery", "allow_flammable",
    "battery_capacity_limit_wh", "require_msds", "fee_mode", "first_fee",
    "first_weight_g", "continue_fee", "continue_unit", "volume_coefficient",
    "delivery_method", "priority_group",
]

# ---------------------------------------------------------------------------
# Helper – rows → list of dicts
# ---------------------------------------------------------------------------
def _rows_to_list(cursor):
    rows = cursor.fetchall()
    if not rows:
        return []
    # sqlite3.Row supports dict() directly
    if hasattr(rows[0], 'keys'):
        return [dict(row) for row in rows]
    # Fallback for plain tuples
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
def health():
    """健康检查接口"""
    return jsonify({"status": "ok"})

# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
@app.route("/api/products", methods=["GET"])
def list_products():
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    try:
        ph = _ph()
        with get_db_connection() as (_, cursor):
            cursor.execute(f"SELECT * FROM products WHERE user_id = {ph}", (_get_user_id(),))
            products = _rows_to_list(cursor)
        return jsonify({"products": products})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/products/<int:product_id>", methods=["GET"])
def get_product(product_id):
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    try:
        product = get_product_by_id(product_id, _get_user_id())
        if not product:
            return jsonify({"error": "Product not found"}), 404
        return jsonify({"product": product})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/products", methods=["POST"])
def create_product():
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    try:
        product_data = {k: data[k] for k in PRODUCT_FIELDS if k in data}
        product_data["user_id"] = _get_user_id()
        product_id = add_product(product_data)
        return jsonify({"product_id": product_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/products/<int:product_id>", methods=["PUT"])
def update_product_route(product_id):
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    try:
        updates = {k: data[k] for k in PRODUCT_FIELDS if k in data}
        if not updates:
            return jsonify({"error": "No valid fields to update"}), 400
        result = update_product(product_id, _get_user_id(), updates)
        if not result:
            return jsonify({"error": "Product not found"}), 404
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
def delete_product_route(product_id):
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    try:
        result = delete_product(product_id, _get_user_id())
        if not result:
            return jsonify({"error": "Product not found"}), 404
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# Logistics rules
# ---------------------------------------------------------------------------
@app.route("/api/logistics", methods=["GET"])
def list_logistics():
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    try:
        ph = _ph()
        with get_db_connection() as (_, cursor):
            cursor.execute(f"SELECT * FROM logistics WHERE user_id = {ph}", (_get_user_id(),))
            rules = _rows_to_list(cursor)
        return jsonify({"logistics": rules})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logistics/<int:rule_id>", methods=["GET"])
def get_logistics(rule_id):
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    try:
        ph = _ph()
        with get_db_connection() as (_, cursor):
            cursor.execute(
                f"SELECT * FROM logistics WHERE id = {ph} AND user_id = {ph}",
                (rule_id, _get_user_id()),
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "Logistics rule not found"}), 404
            result = dict(row) if hasattr(row, 'keys') else dict(zip([d[0] for d in cursor.description], row))
        return jsonify({"logistics": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logistics", methods=["POST"])
def create_logistics():
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    try:
        fields = {k: data[k] for k in LOGISTICS_FIELDS if k in data}
        fields["user_id"] = _get_user_id()
        ph = _ph()
        cols = ", ".join(fields.keys())
        placeholders = ", ".join([ph] * len(fields))
        with get_db_connection() as (conn, cursor):
            cursor.execute(
                f"INSERT INTO logistics ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()
            rule_id = cursor.lastrowid
        return jsonify({"rule_id": rule_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logistics/<int:rule_id>", methods=["PUT"])
def update_logistics(rule_id):
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    try:
        updates = {k: data[k] for k in LOGISTICS_FIELDS if k in data}
        if not updates:
            return jsonify({"error": "No valid fields to update"}), 400
        ph = _ph()
        set_clause = ", ".join(f"{k} = {ph}" for k in updates.keys())
        values = list(updates.values()) + [rule_id, _get_user_id()]
        with get_db_connection() as (conn, cursor):
            cursor.execute(
                f"UPDATE logistics SET {set_clause} WHERE id = {ph} AND user_id = {ph}",
                values,
            )
            conn.commit()
            affected = cursor.rowcount
        if affected == 0:
            return jsonify({"error": "Logistics rule not found"}), 404
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/logistics/<int:rule_id>", methods=["DELETE"])
def delete_logistics(rule_id):
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    try:
        ph = _ph()
        with get_db_connection() as (conn, cursor):
            cursor.execute(
                f"DELETE FROM logistics WHERE id = {ph} AND user_id = {ph}",
                (rule_id, _get_user_id()),
            )
            conn.commit()
            affected = cursor.rowcount
        if affected == 0:
            return jsonify({"error": "Logistics rule not found"}), 404
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# Pricing helpers
# ---------------------------------------------------------------------------

def build_breakdown(product, logistics_cost, final_price, commission_rub, rate):
    """构建成本分解明细列表"""
    items = [
        ("进货单价", product.get("unit_price", 0), "#FF6B6B"),
        ("贴标费用", product.get("labeling_fee", 0), "#4ECDC4"),
        ("供货运费", product.get("shipping_fee", 0), "#45B7D1"),
        ("物流运费", logistics_cost, "#FFA07A"),
        ("代理费", commission_rub * rate, "#98D8C8"),
        ("推广费", final_price * product.get("promotion_cost_rate", 0), "#F7DC6F"),
        ("佣金", final_price * product.get("commission_rate", 0.08), "#BB8FCE"),
        ("提现费", final_price * product.get("withdrawal_fee_rate", 0.02), "#85C1E2"),
        ("收单费", final_price * product.get("payment_processing_fee", 0), "#F8B739"),
        ("退货损失", final_price * product.get("return_rate", 0), "#EB984E"),
        ("增值税", final_price * product.get("vat_rate", 0), "#A569BD"),
    ]
    total_costs = sum(v for _, v, _ in items)
    profit = final_price - total_costs
    items.append(("运营利润", profit, "#52BE80"))
    return [{"label": l, "value": round(v, 2), "color": c} for l, v, c in items if abs(v) > 0.01]


def format_result(res, product_dict, rate, is_land=True):
    """将 calculate_pricing 的结果格式化为 API 响应结构"""
    if is_land:
        price = res.get("land_price")
        cost = res.get("land_cost")
        best_log = res.get("best_land") or {}
        expected_profit = res.get("land_expected_profit", 0)
        pricing_mode = res.get("land_pricing_mode", "")
        commission_info = res.get("land_commission_info", 0)
    else:
        price = res.get("air_price")
        cost = res.get("air_cost")
        best_log = res.get("best_air") or {}
        expected_profit = res.get("air_expected_profit", 0)
        pricing_mode = res.get("air_pricing_mode", "")
        commission_info = res.get("air_commission_info", 0)

    if price is None:
        return None

    commission_rub = commission_info if isinstance(commission_info, (int, float)) else 0
    cost_val = cost if isinstance(cost, (int, float)) else 0

    return {
        "price_cny": round(price, 2),
        "price_rub": round(price / rate, 2) if rate else 0,
        "logistics_name": best_log.get("name", "") if isinstance(best_log, dict) else "",
        "logistics_cost": round(cost_val, 4),
        "days_min": best_log.get("min_days", 0) if isinstance(best_log, dict) else 0,
        "days_max": best_log.get("max_days", 0) if isinstance(best_log, dict) else 0,
        "profit_cny": round(expected_profit, 2),
        "profit_margin_pct": round(expected_profit / price * 100, 2) if price > 0 else 0,
        "commission_rub": round(commission_rub, 2),
        "pricing_mode": pricing_mode,
        "breakdown": build_breakdown(product_dict, cost_val, price, commission_rub, rate),
    }


def do_calculate(product_dict, user_id):
    """执行完整的定价计算，返回 8 种组合结果"""
    ph = _ph()
    with get_db_connection() as (_, cursor):
        cursor.execute(f"SELECT * FROM logistics WHERE user_id = {ph}", (user_id,))
        rules = _rows_to_list(cursor)

    land_rules = [r for r in rules if r.get("type") == "land"]
    air_rules = [r for r in rules if r.get("type") == "air"]

    land_pickup = pd.DataFrame([r for r in land_rules if r.get("delivery_method") == "pickup_point"])
    land_home = pd.DataFrame([r for r in land_rules if r.get("delivery_method") == "home_delivery"])
    air_pickup = pd.DataFrame([r for r in air_rules if r.get("delivery_method") == "pickup_point"])
    air_home = pd.DataFrame([r for r in air_rules if r.get("delivery_method") == "home_delivery"])

    rate = get_fallback_exchange_rate()
    usd_rate = get_fallback_usd_rate()

    all_results = {}
    for priority in ["低价优先", "速度优先"]:
        key = "price_priority" if priority == "低价优先" else "speed_priority"
        combos = {
            "land_pickup": (land_pickup, pd.DataFrame(), True),
            "land_home": (land_home, pd.DataFrame(), True),
            "air_pickup": (pd.DataFrame(), air_pickup, False),
            "air_home": (pd.DataFrame(), air_home, False),
        }
        priority_results = {}
        for combo_key, (land_df, air_df, is_land) in combos.items():
            res = calculate_pricing(product_dict, land_df, air_df, priority)
            priority_results[combo_key] = format_result(res, product_dict, rate, is_land=is_land)
        all_results[key] = priority_results

    return {
        "results": all_results,
        "exchange_rates": {"rub_cny": rate, "usd_cny": usd_rate},
        "product": product_dict,
    }

# ---------------------------------------------------------------------------
# Pricing endpoints
# ---------------------------------------------------------------------------
@app.route("/api/calculate/<int:product_id>", methods=["POST"])
def calculate_by_id(product_id):
    """根据已保存商品 ID 执行定价计算"""
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    try:
        uid = _get_user_id()
        product = get_product_by_id(product_id, uid)
        if not product:
            return jsonify({"error": "Product not found"}), 404
        result = do_calculate(product, uid)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/quick-calculate", methods=["POST"])
def quick_calculate():
    """根据请求体中的商品数据执行定价计算（不保存）"""
    auth_err = _require_auth()
    if auth_err:
        return auth_err
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400
    try:
        product_dict = {k: data[k] for k in PRODUCT_FIELDS if k in data}
        uid = int(data["user_id"]) if "user_id" in data else _get_user_id()
        product_dict.setdefault("user_id", uid)
        result = do_calculate(product_dict, uid)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
