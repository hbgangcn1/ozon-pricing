import hashlib
import math
import os
import sqlite3
import threading

import streamlit as st

from exchange_service import ExchangeRateService
from ui_products import products_page
from ui_logistics import logistics_page
from ui_pricing import pricing_calculator_page
from ui_user import user_management_page, login_or_register_page
from db_utils import init_db

# 线程局部存储
thread_local = threading.local()

# 莫斯科交易所拉取离岸人民币-卢布实时成交价
CACHE_PATH = os.path.join(
    os.path.dirname(
        os.path.abspath(__file__)),
    "moex_rate.json")

# 这里不再定义 get_db，也不再直接用 get_db、conn、c


def create_user(username, password, role="user", email=None):
    """创建用户"""
    conn, c = init_db()  # Assuming init_db returns conn and c
    hashed = hashlib.sha256(password.encode()).hexdigest()
    try:
        c.execute(
            "INSERT INTO users (username, password, role, email) "
            "VALUES (?, ?, ?, ?)",
            (username, hashed, role, email),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(identifier, password):
    """验证用户"""
    conn, c = init_db()  # Assuming init_db returns conn and c
    hashed = hashlib.sha256(password.encode()).hexdigest()
    user = c.execute(
        "SELECT * FROM users "
        "WHERE (username = ? OR email = ?) AND password = ?",
        (
            identifier,
            identifier,
            hashed,
        ),
    ).fetchone()
    return dict(user) if user else None


def current_user_id():
    """获取当前用户ID"""
    return st.session_state.user["id"]


def calculate_logistic_cost(logistic, product, debug=False):
    """计算物流成本"""
    debug_info = []
    # 计算体积重量
    length_cm = product.get("length_cm", 0)
    width_cm = product.get("width_cm", 0)
    height_cm = product.get("height_cm", 0)
    volume_mode = logistic.get("volume_mode", "none")
    volume_coefficient = logistic.get("volume_coefficient", 5000)
    debug_info.append(f"体积重量模式: {volume_mode}, 系数: {volume_coefficient}")

    if volume_mode == "max_actual_vs_volume":
        volume_weight = (length_cm * width_cm * height_cm) / volume_coefficient
        actual_weight = product.get("weight_g", 0) / 1000  # 转换为千克
        calculated_weight = max(actual_weight, volume_weight) * 1000  # 转换回克
        debug_info.append(
            f"实际重量: {actual_weight * 1000:.2f}g, "
            f"体积重量: {volume_weight * 1000:.2f}g, "
            f"计费重量: {calculated_weight:.2f}g"
        )
    else:
        calculated_weight = product.get("weight_g", 0)
        debug_info.append(f"实际重量: {calculated_weight}g（未启用体积重量）")

    # 基础限制
    w = calculated_weight
    min_w = logistic.get("min_weight", 0)
    max_w = logistic.get("max_weight", 10**9)
    debug_info.append(f"重量限制: {min_w}g ~ {max_w}g, 当前: {w}g")
    if w < min_w or w > max_w:
        debug_info.append("不满足重量限制，返回 None")
        return (None, debug_info) if debug else None

    try:
        sides = [
            product.get("length_cm", 0),
            product.get("width_cm", 0),
            product.get("height_cm", 0),
        ]
        debug_info.append(f"三边: {sides}, 三边和: {sum(sides)}, 最长边: {max(sides)}")

        # 判断是标准包装还是圆柱形包装
        has_cylinder_limits = (
            logistic.get("max_cylinder_sum", 0) > 0
            or logistic.get("max_cylinder_length", 0) > 0
            or logistic.get("min_cylinder_length", 0) > 0
        )

        if has_cylinder_limits:
            # 圆柱形包装限制
            cylinder_diameter = product.get("cylinder_diameter", 0)
            cylinder_length = product.get("length_cm", 0)
            cylinder_sum = 2 * cylinder_diameter + cylinder_length

            debug_info.append(
                f"圆柱形包装: 直径={cylinder_diameter}cm, "
                f"长度={cylinder_length}cm, "
                f"2倍直径+长度={cylinder_sum}cm"
            )

            max_cylinder_sum = logistic.get("max_cylinder_sum", 0)
            if max_cylinder_sum > 0 and cylinder_sum > max_cylinder_sum:
                debug_info.append(
                    (
                        "2倍直径与长度之和 "
                        f"{cylinder_sum}cm 超限 {max_cylinder_sum}cm，"
                        "返回 None"
                    )
                )
                return (None, debug_info) if debug else None

            max_cylinder_length = logistic.get("max_cylinder_length", 0)
            if (
                max_cylinder_length > 0
                and cylinder_length > max_cylinder_length
            ):
                debug_info.append(
                    (
                        "圆柱长度 "
                        f"{cylinder_length}cm 超限 {max_cylinder_length}cm，"
                        "返回 None"
                    )
                )
                return (None, debug_info) if debug else None

            min_cylinder_length = logistic.get("min_cylinder_length", 0)
            if (
                min_cylinder_length > 0
                and cylinder_length < min_cylinder_length
            ):
                debug_info.append(
                    (
                        "圆柱长度 "
                        f"{cylinder_length}cm 低于下限 {min_cylinder_length}cm，"
                        "返回 None"
                    )
                )
                return (None, debug_info) if debug else None
        else:
            # 标准包装限制
            if sum(sides) > logistic.get("max_sum_of_sides", 10**9):
                debug_info.append("三边和超限，返回 None")
                return (None, debug_info) if debug else None
            if max(sides) > logistic.get("max_longest_side", 10**9):
                debug_info.append("最长边超限，返回 None")
                return (None, debug_info) if debug else None

            # 第二边长上限检查
            max_second_side = logistic.get("max_second_side", 0)
            if max_second_side > 0:
                sorted_sides = sorted(sides, reverse=True)
                second_side = sorted_sides[1] if len(sorted_sides) > 1 else 0
                debug_info.append(
                    f"第二边长: {second_side}cm, 限制: {max_second_side}cm"
                )
                if second_side > max_second_side:
                    debug_info.append(
                        f"第二边长 {second_side}cm 超限 {max_second_side}cm，返回 None"
                    )
                    return (None, debug_info) if debug else None

            # 长度下限检查
            min_length = logistic.get("min_length", 0)
            if min_length > 0:
                length = product.get("length_cm", 0)
                debug_info.append(f"长度: {length}cm, 下限: {min_length}cm")
                if length < min_length:
                    debug_info.append(
                        f"长度 {length}cm 低于下限 {min_length}cm，返回 None"
                    )
                    return (None, debug_info) if debug else None

        if product.get("has_battery") and not logistic.get("allow_battery"):
            debug_info.append("产品含电池但物流不允许，返回 None")
            return (None, debug_info) if debug else None
        if product.get("has_flammable") and not logistic.get(
                "allow_flammable"):
            debug_info.append("产品含易燃液体但物流不允许，返回 None")
            return (None, debug_info) if debug else None

        # 电池容量 & MSDS
        if product.get("has_battery"):
            limit_wh = logistic.get("battery_capacity_limit_wh", 0)
            if limit_wh > 0:
                wh = product.get("battery_capacity_wh", 0)
                if wh == 0:
                    mah = product.get("battery_capacity_mah", 0)
                    v = product.get("battery_voltage", 0)
                    wh = mah * v / 1000.0
                debug_info.append(f"电池容量: {wh}Wh, 限制: {limit_wh}Wh")
                if wh > limit_wh:
                    debug_info.append("电池容量超限，返回 None")
                    return (None, debug_info) if debug else None
            if logistic.get("require_msds") and not product.get("has_msds"):
                debug_info.append("要求 MSDS 但产品未提供，返回 None")
                return (None, debug_info) if debug else None
    except Exception as e:
        debug_info.append(f"计算物流成本时出错: {str(e)}")
        if debug:
            return (None, debug_info)
        else:
            st.error(f"计算物流成本时出错: {str(e)}")
            return None

    # 重量计费
    w = product.get("weight_g", 0)
    fee_mode = logistic.get("fee_mode", "base_plus_continue")
    continue_unit = int(logistic.get("continue_unit", 100))
    continue_fee = logistic.get("continue_fee", 0)
    debug_info.append(
        f"计费方式: {fee_mode}, 续重单位: {continue_unit}g, 续重费用: {continue_fee}"
    )

    if fee_mode == "base_plus_continue":
        units = math.ceil(w / continue_unit)
        cost = logistic.get("base_fee", 0) + continue_fee * units
        debug_info.append(
            f"基础费用: {logistic.get('base_fee', 0)}, "
            f"单位数: {units}, 运费: {cost}"
        )
    else:  # first_plus_continue
        first_weight = logistic.get("first_weight_g", 0)
        first_fee = logistic.get("first_fee", 0)
        if w <= first_weight:
            cost = first_fee
            debug_info.append(f"首重费用: {first_fee}，在首重范围内")
        else:
            extra_units = math.ceil((w - first_weight) / continue_unit)
            cost = first_fee + continue_fee * extra_units
            debug_info.append(
                f"首重费用: {first_fee}，超出部分单位数: {extra_units}，总运费: {cost}"
            )

    # 限价判断（人民币→卢布）
    try:
        rate = ExchangeRateService().get_exchange_rate()  # 1 CNY = x RUB
        unit_price = float(product.get("unit_price", 0))
        labeling_fee = float(product.get("labeling_fee", 0))
        shipping_fee = float(product.get("shipping_fee", 0))
        total_cny = unit_price + labeling_fee + shipping_fee + 15 * rate + cost
        rough_cny = (
            total_cny
            * (1 + product.get("target_profit_margin", 0))
            / (
                (1 - product.get("promotion_discount", 0))
                * (1 - product.get("commission_rate", 0))
                * (1 - product.get("withdrawal_fee_rate", 0))
                * (1 - product.get("payment_processing_fee", 0))
            )
        )
        rough_rub = rough_cny / rate
        limit_rub = logistic.get("price_limit_rub") or 0
        min_rub = logistic.get("price_min_rub") or 0
        debug_info.append(
            f"限价判断: 估算售价 {rough_rub:.2f} RUB, "
            f"上限 {limit_rub} RUB, 下限 {min_rub} RUB"
        )
        if 0 < limit_rub < rough_rub:
            debug_info.append("超价格上限，返回 None")
            return (None, debug_info) if debug else None
        if 0 < min_rub > rough_rub:
            debug_info.append("低于价格下限，返回 None")
            return (None, debug_info) if debug else None
    except Exception as e:
        debug_info.append(f"限价判断出错: {e}")
        if debug:
            return (None, debug_info)
        else:
            st.error(f"限价判断出错: {e}")
            return None

    debug_info.append(f"最终运费: {cost}")
    return (cost, debug_info) if debug else cost


def calculate_pricing(product, land_logistics, air_logistics):
    """计算定价"""
    import time
    from functools import lru_cache

    start_total = time.time()

    # 1. 基础数据
    t0 = time.time()
    unit_price = float(product["unit_price"])
    labeling_fee = float(product["labeling_fee"])
    shipping_fee = float(product["shipping_fee"])
    rate = ExchangeRateService().get_exchange_rate()
    print(f"[TIME] 基础数据读取: {(time.time() - t0) * 1000:.2f} ms")

    # 2. 缓存版 calculate_logistic_cost
    @lru_cache(maxsize=256)
    def cached_cost(log_tuple, prod_tuple):
        return calculate_logistic_cost(
            dict(log_tuple), dict(prod_tuple), debug=True)

    # 3. 过滤可用物流
    t0 = time.time()

    all_costs_debug = []

    def _cost_and_filter(logistics):
        res = []
        for log in logistics:
            cost, debug_info = cached_cost(
                tuple(
                    log.items()), tuple(
                    product.items()))
            all_costs_debug.append(
                {"logistic": log, "cost": cost, "debug": debug_info})
            if cost is None:
                continue
            limit = log.get("price_limit") or 0
            # 粗略估算价格
            rough = (
                (unit_price + labeling_fee + shipping_fee + 15 * rate + cost)
                * (1 + product["target_profit_margin"])
                / (
                    (1 - product["promotion_discount"])
                    * (1 - product["commission_rate"])
                    * (1 - product["withdrawal_fee_rate"])
                    * (1 - product["payment_processing_fee"])
                )
            )
            if limit == 0 or rough <= limit:
                res.append((log, cost))
        return res

    land_candidates = _cost_and_filter(land_logistics)
    air_candidates = _cost_and_filter(air_logistics)
    print(f"[TIME] 物流过滤: {(time.time() - t0) * 1000:.2f} ms")

    # 4. 取最优
    t0 = time.time()
    land_best = (
        min(land_candidates, key=lambda x: x[1])
        if land_candidates
        else (None, None)
    )
    air_best = (
        min(air_candidates, key=lambda x: x[1])
        if air_candidates
        else (None, None)
    )

    # 5. 最终价格
    def _final_price(cost, debug_list=None):
        total_cost = (
            unit_price
            + labeling_fee
            + shipping_fee
            + cost
            + 15 * rate
        )
        denominator = (
            (1 - product["promotion_discount"])
            * (1 - product["commission_rate"])
            * (1 - product["withdrawal_fee_rate"])
            * (1 - product["payment_processing_fee"])
        )
        price = round(
            total_cost * (1 + product["target_profit_margin"]) / denominator, 2
        )
        if debug_list is not None:
            debug_list.append(
                "定价公式: (("
                f"{total_cost:.2f}) * (1 + "
                f"{product['target_profit_margin']})"
                ") / "
                f"{denominator:.4f} = "
                f"{price:.2f}"
            )
        return price

    land_debug = []
    air_debug = []
    land_price = _final_price(land_best[1],
                              land_debug) if land_best[0] else None
    air_price = _final_price(air_best[1], air_debug) if air_best[0] else None
    print(f"[TIME] 价格计算: {(time.time() - t0) * 1000:.2f} ms")

    print(f"[TIME] 总耗时: {(time.time() - start_total) * 1000:.2f} ms")
    return (
        land_price,
        air_price,
        land_best[1] if land_best[0] else None,
        air_best[1] if air_best[0] else None,
        land_best[0]["name"] if land_best[0] else None,
        air_best[0]["name"] if air_best[0] else None,
        all_costs_debug,  # 新增：所有物流的运费和调试信息
        land_debug,  # 新增：陆运定价调试信息
        air_debug,  # 新增：空运定价调试信息
    )


def main():
    st.set_page_config(page_title="物流定价系统", page_icon="📦", layout="wide")
    st.sidebar.subheader("调试信息")
    st.session_state.debug_mode = st.sidebar.checkbox("启用调试模式", False)
    init_db()
    if "user" not in st.session_state:
        st.session_state.user = None
    if st.session_state.user is None:
        login_or_register_page()
        return
    st.sidebar.title(f"欢迎, {st.session_state.user['username']}")
    st.sidebar.subheader(f"角色: {st.session_state.user['role']}")
    menu_options = ["产品管理", "物流规则", "定价计算器"]
    if st.session_state.user["role"] == "admin":
        menu_options.append("用户管理")
    selected_page = st.sidebar.selectbox("导航", menu_options)
    if selected_page == "产品管理":
        products_page()
    elif selected_page == "物流规则":
        logistics_page()
    elif selected_page == "定价计算器":
        pricing_calculator_page()
    elif selected_page == "用户管理":
        user_management_page()
    if st.sidebar.button("退出登录", key="logout"):
        st.session_state.user = None
        st.session_state.pop("products_data", None)
        st.session_state.pop("logistics_data", None)
        st.rerun()


def _debug_filter_reason(logistic: dict, product: dict) -> str | None:
    """检查物流被淘汰的原因"""
    """
    返回物流被淘汰的详细原因；若完全可用则返回 None。
    与 calculate_logistic_cost() 的判断逻辑保持 100% 一致。
    """

    # ---------- 1. 重量 ----------
    w = product.get("weight_g", 0)
    min_w = logistic.get("min_weight", 0)
    max_w = logistic.get("max_weight", 10**9)
    if w < min_w:
        return f"重量 {w} g 低于下限 {min_w} g"
    if w > max_w:
        return f"重量 {w} g 高于上限 {max_w} g"

    # ---------- 2. 边长 ----------
    sides = [
        product.get("length_cm", 0),
        product.get("width_cm", 0),
        product.get("height_cm", 0),
    ]

    # 判断是标准包装还是圆柱形包装
    has_cylinder_limits = (
        logistic.get("max_cylinder_sum", 0) > 0
        or logistic.get("max_cylinder_length", 0) > 0
        or logistic.get("min_cylinder_length", 0) > 0
    )

    if has_cylinder_limits:
        # 圆柱形包装限制
        cylinder_diameter = product.get("cylinder_diameter", 0)
        cylinder_length = product.get("length_cm", 0)
        cylinder_sum = 2 * cylinder_diameter + cylinder_length

        max_cylinder_sum = logistic.get("max_cylinder_sum", 0)
        if max_cylinder_sum > 0 and cylinder_sum > max_cylinder_sum:
            return f"2倍直径与长度之和 {cylinder_sum} cm 超过限制 {max_cylinder_sum} cm"

        max_cylinder_length = logistic.get("max_cylinder_length", 0)
        if (
            max_cylinder_length > 0
            and cylinder_length > max_cylinder_length
        ):
            return f"圆柱长度 {cylinder_length} cm 超过限制 {max_cylinder_length} cm"

        min_cylinder_length = logistic.get("min_cylinder_length", 0)
        if min_cylinder_length > 0 and cylinder_length < min_cylinder_length:
            return f"圆柱长度 {cylinder_length} cm 低于下限 {min_cylinder_length} cm"
    else:
        # 标准包装限制
        max_sum = logistic.get("max_sum_of_sides", 10**9)
        if sum(sides) > max_sum:
            return f"三边之和 {sum(sides)} cm 超过限制 {max_sum} cm"
        max_long = logistic.get("max_longest_side", 10**9)
        if max(sides) > max_long:
            return f"最长边 {max(sides)} cm 超过限制 {max_long} cm"

        # 第二边长上限检查
        max_second_side = logistic.get("max_second_side", 0)
        if max_second_side > 0:
            sorted_sides = sorted(sides, reverse=True)
            second_side = sorted_sides[1] if len(sorted_sides) > 1 else 0
            if second_side > max_second_side:
                return f"第二边长 {second_side} cm 超过限制 {max_second_side} cm"

        # 长度下限检查
        min_length = logistic.get("min_length", 0)
        if min_length > 0:
            length = product.get("length_cm", 0)
            if length < min_length:
                return f"长度 {length} cm 低于下限 {min_length} cm"

    # 3. 特殊物品
    if product.get("has_battery") and not logistic.get("allow_battery"):
        return "产品含电池但物流不允许电池"
    if product.get("has_flammable") and not logistic.get("allow_flammable"):
        return "产品含易燃液体但物流不允许易燃液体"

    # 4. 电池容量 & MSDS
    if product.get("has_battery"):
        limit_wh = logistic.get("battery_capacity_limit_wh", 0)
        if limit_wh > 0:
            wh = product.get("battery_capacity_wh", 0)
            if wh == 0:
                mah = product.get("battery_capacity_mah", 0)
                v = product.get("battery_voltage", 0)
                wh = mah * v / 1000.0
            if wh > limit_wh:
                return f"电池容量 {wh} Wh 超过物流限制 {limit_wh} Wh"
        if logistic.get("require_msds") and not product.get("has_msds"):
            return "物流要求 MSDS 但产品未提供"

    # 5. 限价（人民币→卢布）
    try:
        rate = ExchangeRateService().get_exchange_rate()  # 1 CNY = x RUB
        unit_price = float(product.get("unit_price", 0))
        labeling_fee = float(product.get("labeling_fee", 0))
        shipping_fee = float(product.get("shipping_fee", 0))

        # 先计算运费（复用与正式计算完全一致的公式）
        w = product.get("weight_g", 0)
        fee_mode = logistic.get("fee_mode", "base_plus_continue")
        continue_unit = int(logistic.get("continue_unit", 100))

        if fee_mode == "base_plus_continue":
            units = __import__("math").ceil(w / continue_unit)
            cost = logistic.get("base_fee", 0) + \
                logistic.get("continue_fee", 0) * units
        else:  # first_plus_continue
            first_w = logistic.get("first_weight_g", 0)
            first_cost = logistic.get("first_fee", 0)
            cost = (
                first_cost
                if w <= first_w
                else first_cost
                + __import__("math").ceil((w - first_w) / continue_unit)
                * logistic.get("continue_fee", 0)
            )

        # 估算人民币总成本
        total_cny = unit_price + labeling_fee + shipping_fee + 15 * rate + cost
        # 估算人民币售价
        denominator = (
            (1 - product.get("promotion_discount", 0))
            * (1 - product.get("commission_rate", 0))
            * (1 - product.get("withdrawal_fee_rate", 0))
            * (1 - product.get("payment_processing_fee", 0))
        )
        if denominator == 0:
            return "费率参数异常导致除以 0"
        rough_cny = (
            total_cny
            * (1 + product.get("target_profit_margin", 0))
            / denominator
        )
        rough_rub = rough_cny / rate
        limit_rub = logistic.get("price_limit_rub", 0)
        min_rub = logistic.get("price_min_rub", 0)
        if 0 < limit_rub < rough_rub:
            return f"估算售价 {rough_rub:.2f} RUB 超价格上限 {limit_rub} RUB"
        if 0 < min_rub > rough_rub:
            return f"估算售价 {rough_rub:.2f} RUB 低于价格下限 {min_rub} RUB"
    except Exception as e:
        return f"限价判断异常: {e}"

    # 6. 全部通过
    return None


if __name__ == "__main__":
    main()
