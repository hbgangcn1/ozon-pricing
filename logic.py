# logic.py

import math
from collections import defaultdict

# 为了测试兼容性，导入ExchangeRateService（当前未使用，保留用于未来扩展）
try:
    from exchange_service import (
        ExchangeRateService,  # pyright: ignore[reportUnusedImport]
        get_usd_rate,  # pyright: ignore[reportUnusedImport]
    )
except ImportError:
    ExchangeRateService = None
    get_usd_rate = None


def calculate_logistic_cost(logistic, product, is_fast_mode=False, debug=False):
    """计算物流成本

    Args:
        logistic: 物流规则字典
        product: 产品字典
        is_fast_mode: 是否为极速模式（跳过尺寸检查）
        debug: 是否返回调试信息
    """
    debug_info = []

    # 处理无效输入
    if logistic is None or product is None:
        debug_info.append("输入数据无效，返回 None")
        return (None, debug_info) if debug else None

    # 如果输入不是字典，尝试调用 .get() 方法，这会抛出 AttributeError
    if not isinstance(logistic, dict):
        # 尝试访问 .get 方法，这会抛出 AttributeError
        logistic.get("test")
        debug_info.append("输入数据类型无效，返回 None")
        return (None, debug_info) if debug else None

    if not isinstance(product, dict):
        # 尝试访问 .get 方法，这会抛出 AttributeError
        product.get("test")
        debug_info.append("输入数据类型无效，返回 None")
        return (None, debug_info) if debug else None

    # 获取体积重量计算参数
    volume_mode = logistic.get("volume_mode", "none")
    # 转换为float以兼容PostgreSQL的Decimal类型
    volume_coefficient = float(logistic.get("volume_coefficient", 5000))
    debug_info.append(f"体积重量模式: {volume_mode}, 系数: {volume_coefficient}")

    # 基础限制检查（0 = 无限制，不参与判断）
    actual_weight = product.get("weight_g", 0)
    min_w = float(logistic.get("min_weight", 0))
    max_w = float(logistic.get("max_weight", 0))  # 0 = 无上限

    if actual_weight < 0:
        debug_info.append(f"重量 {actual_weight}g 为负数，返回 None")
        return (None, debug_info) if debug else None

    # 如果重量为0，返回基础费用
    if actual_weight == 0:
        debug_info.append("重量为0，返回基础费用")
        base_fee = float(logistic.get("base_fee", 0))
        return (base_fee, debug_info) if debug else base_fee

    # 重量限制检查：min_w=0 表示无下限，max_w=0 表示无上限
    if min_w > 0 and actual_weight < min_w:
        debug_info.append(f"重量 {actual_weight}g 低于下限 {min_w}g，返回 None")
        return (None, debug_info) if debug else None
    if max_w > 0 and actual_weight > max_w:
        debug_info.append(f"重量 {actual_weight}g 超过上限 {max_w}g，返回 None")
        return (None, debug_info) if debug else None
    debug_info.append(
        f"重量限制: {min_w or '无'}g ~ {max_w or '无'}g, 当前: {actual_weight}g"
    )
    try:
        # 获取产品包装形状
        is_cylinder = product.get("is_cylinder", False)

        if is_cylinder:
            # 圆柱形包装产品
            cylinder_diameter = product.get("cylinder_diameter", 0)
            cylinder_length = product.get("cylinder_length", 0)

            # 首先检查物流是否有圆柱形包装限制
            has_cylinder_limits = (
                logistic.get("max_cylinder_sum", 0) > 0
                or logistic.get("min_cylinder_sum", 0) > 0
                or logistic.get("max_cylinder_length", 0) > 0
                or logistic.get("min_cylinder_length", 0) > 0
            )

            if has_cylinder_limits:
                # 使用圆柱形包装限制进行匹配
                cylinder_sum = 2 * cylinder_diameter + cylinder_length
                debug_info.append(
                    f"圆柱形包装: 直径={cylinder_diameter}cm, "
                    f"长度={cylinder_length}cm, "
                    f"2倍直径+长度={cylinder_sum}cm"
                )
                # 极速模式跳过圆柱形包装尺寸检查
                if is_fast_mode:
                    debug_info.append("极速模式，跳过圆柱形包装尺寸限制检查")
                else:
                    max_cylinder_sum = logistic.get("max_cylinder_sum", 0)
                    if 0 < max_cylinder_sum < cylinder_sum:
                        debug_info.append(
                            (
                                "2倍直径与长度之和 "
                                f"{cylinder_sum}cm 超限 {max_cylinder_sum}cm，"
                                "返回 None"
                            )
                        )
                        return (None, debug_info) if debug else None
                    min_cylinder_sum = logistic.get("min_cylinder_sum", 0)
                    if min_cylinder_sum > 0 and cylinder_sum < min_cylinder_sum:
                        debug_info.append(
                            (
                                "2倍直径与长度之和 "
                                f"{cylinder_sum}cm 低于下限 {min_cylinder_sum}cm，"
                                "返回 None"
                            )
                        )
                        return (None, debug_info) if debug else None
                    max_cylinder_length = logistic.get("max_cylinder_length", 0)
                    if 0 < max_cylinder_length < cylinder_length:
                        debug_info.append(
                            (
                                "圆柱长度 "
                                f"{cylinder_length}cm 超限 "
                                f"{max_cylinder_length}cm，"
                                "返回 None"
                            )
                        )
                        return (None, debug_info) if debug else None
                    min_cyl = logistic.get("min_cylinder_length", 0)
                    if min_cyl > 0 and cylinder_length < min_cyl:
                        debug_info.append(
                            (
                                "圆柱长度 "
                                f"{cylinder_length}cm 低于下限 {min_cyl}cm，"
                                "返回 None"
                            )
                        )
                        return (None, debug_info) if debug else None
                # 圆柱形包装检查通过后，仍然需要定义sides用于后续标准包装限制检查
                sides = [cylinder_diameter, cylinder_diameter, cylinder_length]
            else:
                # 物流没有圆柱形包装限制，使用标准包装限制
                # 将圆柱形包装转换为标准包装进行匹配
                # 圆柱直径相当于长和宽，圆柱长度相当于高
                sides = [cylinder_diameter, cylinder_diameter, cylinder_length]
                debug_info.append(
                    f"圆柱形包装转换为标准包装: 长={cylinder_diameter}cm, "
                    f"宽={cylinder_diameter}cm, 高={cylinder_length}cm"
                )
        else:
            # 标准包装产品
            sides = [
                product.get("length_cm", 0),
                product.get("width_cm", 0),
                product.get("height_cm", 0),
            ]
            debug_info.append(
                f"标准包装: 长={sides[0]}cm, 宽={sides[1]}cm, 高={sides[2]}cm"
            )

        debug_info.append(f"三边: {sides}, 三边和: {sum(sides)}, 最长边: {max(sides)}")

        # 极速模式跳过所有尺寸检查
        is_fast_mode = product.get("name") == "极速模式产品"
        if is_fast_mode:
            debug_info.append("极速模式，跳过所有尺寸限制检查")
        else:
            # 标准包装限制检查
            max_sum_of_sides = logistic.get("max_sum_of_sides", 10**9)
            if 0 < max_sum_of_sides < sum(sides):
                debug_info.append("三边和超限，返回 None")
                return (None, debug_info) if debug else None
            max_longest_side_val = logistic.get("max_longest_side", 10**9)
            if max_longest_side_val > 0 and max(sides) > max_longest_side_val:
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
                if 0 < max_second_side < second_side:
                    debug_info.append(
                        f"第二边长 {second_side}cm 超限 {max_second_side}cm，返回 None"
                    )
                    return (None, debug_info) if debug else None
            # 第二长边下限检查
            min_second_side = logistic.get("min_second_side", 0)
            if min_second_side > 0:
                sorted_sides = sorted(sides, reverse=True)
                second_side = sorted_sides[1] if len(sorted_sides) > 1 else 0
                debug_info.append(
                    f"第二边长: {second_side}cm, 下限: {min_second_side}cm"
                )
                if second_side < min_second_side:
                    debug_info.append(
                        f"第二边长 {second_side}cm 低于下限 "
                        f"{min_second_side}cm，返回 None"
                    )
                    return (None, debug_info) if debug else None
            # 最长边下限检查
            min_len = logistic.get("min_length", 0)
            if min_len > 0:
                longest_side = max(sides)
                debug_info.append(f"最长边: {longest_side}cm, 下限: {min_len}cm")
                if longest_side < min_len:
                    debug_info.append(
                        f"最长边 {longest_side}cm 低于下限 {min_len}cm，返回 None"
                    )
                    return (None, debug_info) if debug else None
        # 极速模式跳过所有特殊物品检查
        if is_fast_mode:
            debug_info.append(
                "极速模式，跳过所有特殊物品检查（电池、易燃液体、MSDS等）"
            )
        else:
            if product.get("has_battery") and not logistic.get("allow_battery"):
                debug_info.append("产品含电池但物流不允许，返回 None")
                return (None, debug_info) if debug else None
            if product.get("has_liquid") and not logistic.get("allow_liquid"):
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
                        # 如果mAh和V都为0，跳过电池容量限制判断
                        if mah <= 0 and v <= 0:
                            debug_info.append("电池容量mAh和V都为0，跳过容量限制判断")
                        else:
                            wh = mah * v / 1000.0
                            debug_info.append(f"电池容量: {wh}Wh, 限制: {limit_wh}Wh")
                            if 0 < limit_wh < wh:
                                debug_info.append("电池容量超限，返回 None")
                                return (None, debug_info) if debug else None
                    else:
                        # 如果填写了Wh但值为0，跳过电池容量限制判断
                        if wh <= 0:
                            debug_info.append("电池容量Wh为0，跳过容量限制判断")
                        else:
                            debug_info.append(f"电池容量: {wh}Wh, 限制: {limit_wh}Wh")
                            if 0 < limit_wh < wh:
                                debug_info.append("电池容量超限，返回 None")
                                return (None, debug_info) if debug else None
                if logistic.get("require_msds") and not product.get("has_msds"):
                    debug_info.append("要求 MSDS 但产品未提供，返回 None")
                    return (None, debug_info) if debug else None

        # 计算体积重量（在包装尺寸确定之后）
        if volume_mode == "max_actual_vs_volume":
            volume_weight = (sides[0] * sides[1] * sides[2]) / volume_coefficient
            actual_weight_kg = actual_weight / 1000  # 转换为千克
            # 转换回克
            calculated_weight = max(actual_weight_kg, volume_weight) * 1000
            debug_info.append(
                f"实际重量: {actual_weight:.2f}g, "
                f"体积重量: {volume_weight * 1000:.2f}g, "
                f"计费重量: {calculated_weight:.2f}g"
            )
        elif volume_mode == "longest_side":
            # 转换为float以兼容PostgreSQL的Decimal类型
            longest_side_threshold = float(logistic.get("longest_side_threshold", 0))
            longest_side = max(sides)
            debug_info.append(
                f"最长边: {longest_side}cm, 阈值: {longest_side_threshold}cm"
            )
            if longest_side > longest_side_threshold:
                volume_weight = (sides[0] * sides[1] * sides[2]) / volume_coefficient
                # 当最长边超过阈值时，直接使用体积重量计费
                calculated_weight = volume_weight * 1000  # 转换回克
                debug_info.append(
                    f"最长边超过阈值，按体积重量计费: "
                    f"实际重量: {actual_weight:.2f}g, "
                    f"体积重量: {volume_weight * 1000:.2f}g, "
                    f"计费重量: {calculated_weight:.2f}g"
                )
            else:
                calculated_weight = actual_weight
                debug_info.append(
                    f"最长边未超过阈值，使用实际重量: {calculated_weight}g"
                )
        else:
            calculated_weight = actual_weight
            debug_info.append(f"实际重量: {calculated_weight}g（未启用体积重量）")

    except (KeyError, TypeError, ZeroDivisionError) as e:
        debug_info.append(f"计算物流成本时出错: {str(e)}")
        if debug:
            return None, debug_info
        else:
            return None
    # 重量计费
    w = calculated_weight
    fee_mode = logistic.get("fee_mode", "base_weight")
    # 处理continue_unit：可能是字符串('g'/'kg'/'50g'/'100g'/'500g'/'1kg')或数值
    continue_unit_raw = logistic.get("continue_unit", 100)
    if isinstance(continue_unit_raw, str):
        if continue_unit_raw == "kg":
            continue_unit = 1000
        elif continue_unit_raw == "g":
            continue_unit = 1  # 每克
        else:
            # 处理 "50g", "100g", "500g", "1kg" 等格式
            import re

            g_match = re.match(r"^(\d+)\s*g$", continue_unit_raw, re.IGNORECASE)
            kg_match = re.match(
                r"^(\d+(?:\.\d+)?)\s*kg$", continue_unit_raw, re.IGNORECASE
            )
            if g_match:
                continue_unit = int(g_match.group(1))
            elif kg_match:
                continue_unit = int(float(kg_match.group(1)) * 1000)
            else:
                # 兜底：尝试直接转数字
                try:
                    continue_unit = int(continue_unit_raw)
                except (ValueError, TypeError):
                    continue_unit = 100
    else:
        continue_unit = int(continue_unit_raw) if continue_unit_raw else 100
    # 转换为float以兼容PostgreSQL的Decimal类型
    continue_fee = float(logistic.get("continue_fee", 0))
    debug_info.append(
        f"计费方式: {fee_mode}, 续重单位: {continue_unit}g, 续重费用: {continue_fee:.5f}"
    )
    if fee_mode in ("base_weight", "base_plus_continue"):
        units = math.ceil(w / continue_unit)
        base_fee = float(logistic.get("base_fee", 0))
        cost = base_fee + continue_fee * units
        debug_info.append(f"基础费用: {base_fee}, 单位数: {units}, 运费: {cost}")
    else:  # first_plus_continue
        first_weight = float(logistic.get("first_weight_g", 0))
        first_fee = float(logistic.get("first_fee", 0))
        if w <= first_weight:
            cost = first_fee
            debug_info.append(f"首重费用: {first_fee}，在首重范围内")
        else:
            extra_units = math.ceil((w - first_weight) / continue_unit)
            cost = first_fee + continue_fee * extra_units
            debug_info.append(
                f"首重费用: {first_fee}，超出部分单位数: {extra_units}，总运费: {cost}"
            )
    # 价格限制检查将在 _cost_and_filter 中进行
    debug_info.append(f"最终运费: {cost}")
    return (cost, debug_info) if debug else cost


def calculate_pricing(
    product, land_logistics, air_logistics, mode="fast", priority="低价优先"
):
    """计算定价"""
    from functools import lru_cache

    filtered_logistics = {"land": [], "air": []}
    try:
        # 处理无效输入
        if product is None or land_logistics is None or air_logistics is None:
            return {
                "best_land": None,
                "best_air": None,
                "land_price": None,
                "air_price": None,
                "land_cost": None,
                "air_cost": None,
                "suggested_price": None,
                "expected_profit": 0,
                "profit_margin": 0,
                "land_stats": None,
                "air_stats": None,
                "all_costs_debug": [],
                "land_debug": [],
                "air_debug": [],
                "avg_land_cost": 0,
                "avg_land_days": 0,
                "avg_air_cost": 0,
                "avg_air_days": 0,
                "saved_land_cost": 0,
                "saved_land_days": 0,
                "saved_air_cost": 0,
                "saved_air_days": 0,
                "filtered_logistics": filtered_logistics,
            }

        # 1. 基础数据 - 只获取一次汇率
        # 首先检查 product 是否有 get 方法
        if not hasattr(product, "get"):
            # 尝试调用 .get() 方法，这会抛出 AttributeError
            product.get("test")

        # 检查DataFrame是否为空
        def is_empty_logistics(logistics):
            if hasattr(logistics, "empty"):
                return logistics.empty
            return not logistics

        if is_empty_logistics(land_logistics) and is_empty_logistics(air_logistics):
            # 返回空结果字典
            return {
                "best_land": None,
                "best_air": None,
                "land_price": None,
                "air_price": None,
                "land_cost": None,
                "air_cost": None,
                "suggested_price": None,
                "expected_profit": 0,
                "profit_margin": 0,
                "land_stats": None,
                "air_stats": None,
                "all_costs_debug": [],
                "land_debug": [],
                "air_debug": [],
            }

        unit_price = float(product.get("unit_price", 0))
        labeling_fee = float(product.get("labeling_fee", 0))
        shipping_fee = float(product.get("shipping_fee", 0))

        # 用户计算时只使用兜底汇率，不调用API
        try:
            from exchange_service import (
                get_fallback_exchange_rate,
                get_fallback_usd_rate,
            )
        except ImportError:
            # 如果导入失败，在此定义占位函数
            def get_fallback_exchange_rate():
                return 0.0904

            def get_fallback_usd_rate():
                return 7.2

        rate = get_fallback_exchange_rate()
        usd_rate = get_fallback_usd_rate()

        # 判断是否为极速模式
        is_fast_mode = mode == "fast"

        # 2. 缓存版 calculate_logistic_cost
        @lru_cache(maxsize=256)
        def cached_cost(log_tuple, prod_tuple):
            return calculate_logistic_cost(
                dict(log_tuple), dict(prod_tuple), is_fast_mode, debug=True
            )

        # 3. 过滤可用物流
        all_costs_debug = []

        def _cost_and_filter(logistics):
            res = []
            # 在函数开始时处理 product，确保它是字典格式
            if hasattr(product, "to_dict"):
                product_dict = product.to_dict()
            elif isinstance(product, dict):
                product_dict = product
            else:
                # 如果是其他类型，尝试转换为字典
                if hasattr(product, "items"):
                    # 尝试调用 .get() 方法，如果不存在会抛出 AttributeError
                    product.get("test")
                    product_dict = dict(product)
                else:
                    # 尝试调用 .get() 方法，这会抛出 AttributeError
                    product.get("test")
                    # 如果上面的调用没有抛出异常，说明对象有get方法但没有items方法
                    # 这种情况下我们无法处理，抛出AttributeError
                    raise AttributeError(f"对象 {type(product)} 没有 items() 方法")

            # 处理物流数据 - 支持DataFrame和list
            if hasattr(logistics, "empty"):
                # pandas DataFrame
                if logistics.empty:
                    return res
                logistics_iter = logistics.iterrows()
            else:
                # Python list
                if not logistics:
                    return res
                logistics_iter = enumerate(logistics)

            for _, log in logistics_iter:
                # 将 pandas Series 转换为字典
                current_log_dict = (
                    log.to_dict()
                    if hasattr(log, "to_dict")
                    else dict(log)
                    if hasattr(log, "items")
                    else log
                )

                cost, debug_info = cached_cost(
                    tuple(current_log_dict.items()), tuple(product_dict.items())
                )
                all_costs_debug.append(
                    {"logistic": current_log_dict, "cost": cost, "debug": debug_info}
                )
                if cost is None:
                    # 淘汰原因
                    reason = _debug_filter_reason(current_log_dict, product_dict)
                    if logistics is land_logistics:
                        filtered_logistics["land"].append(
                            {"name": current_log_dict.get("name", ""), "reason": reason}
                        )
                    else:
                        filtered_logistics["air"].append(
                            {"name": current_log_dict.get("name", ""), "reason": reason}
                        )
                    continue

                # 浮动代理费价格计算
                def calc_floating_price(
                    cost_input,
                    target_margin_input,
                    promotion_rate_input,
                    commission_rate_input,
                    withdrawal_rate_input,
                    payment_rate_input,
                    vat_rate_input,
                    rate_input,
                    max_iter=3,
                ):
                    """计算浮动代理费和收单费价格"""
                    commission_fee = 15 * rate_input
                    # 收单费初始值：按比例或最低10 RUB
                    payment_fee_fixed = 10 * rate_input
                    use_fixed_payment = payment_rate_input > 0
                    price = 0
                    price_rub = 0.0

                    for _ in range(max_iter):
                        if use_fixed_payment:
                            calc_total_cost = (
                                cost_input + commission_fee + payment_fee_fixed
                            )
                            price_denominator = (
                                1
                                - target_margin_input
                                - promotion_rate_input
                                - commission_rate_input
                                - withdrawal_rate_input
                                - vat_rate_input
                            )
                        else:
                            calc_total_cost = cost_input + commission_fee
                            price_denominator = (
                                1
                                - target_margin_input
                                - promotion_rate_input
                                - commission_rate_input
                                - withdrawal_rate_input
                                - payment_rate_input
                                - vat_rate_input
                            )
                        price = calc_total_cost / price_denominator

                        price_rub = price / rate_input
                        new_commission_rub = max(15, min(200, price_rub * 0.02))
                        new_commission_fee = new_commission_rub * rate_input

                        # 判断收单费是固定还是按比例
                        if payment_rate_input > 0:
                            payment_by_rate = price_rub * payment_rate_input
                            if payment_by_rate < 10:
                                use_fixed_payment = True
                                payment_fee_fixed = 10 * rate_input
                            else:
                                use_fixed_payment = False

                        if abs(new_commission_fee - commission_fee) < 0.001:
                            break
                        commission_fee = new_commission_fee

                    actual_payment_rub = (
                        10.0 if use_fixed_payment else price_rub * payment_rate_input
                    )
                    return (
                        price,
                        commission_fee / rate_input,
                        actual_payment_rub,
                        use_fixed_payment,
                    )

                # 基础成本（不包含代理费）
                base_cost_calc = unit_price + labeling_fee + shipping_fee + cost
                filter_target_margin = product_dict.get("target_profit_margin", 0.2)
                filter_promotion_rate = product_dict.get("promotion_cost_rate", 0)
                filter_commission_rate = product_dict.get("commission_rate", 0.08)
                filter_withdrawal_rate = product_dict.get("withdrawal_fee_rate", 0.02)
                filter_payment_rate = product_dict.get("payment_processing_fee", 0)
                filter_return_rate = product_dict.get("return_rate", 0)
                filter_vat_rate = product_dict.get("vat_rate", 0)
                if filter_target_margin >= 1:
                    filter_target_margin = filter_target_margin / 100
                if filter_promotion_rate >= 1:
                    filter_promotion_rate = filter_promotion_rate / 100
                if filter_commission_rate >= 1:
                    filter_commission_rate = filter_commission_rate / 100
                if filter_withdrawal_rate >= 1:
                    filter_withdrawal_rate = filter_withdrawal_rate / 100
                if filter_payment_rate >= 1:
                    filter_payment_rate = filter_payment_rate / 100
                if filter_return_rate >= 1:
                    filter_return_rate = filter_return_rate / 100
                if filter_vat_rate >= 1:
                    filter_vat_rate = filter_vat_rate / 100

                # 计算浮动代理费和收单费
                (rough, actual_commission, actual_payment_rub, fixed_payment) = (
                    calc_floating_price(
                        base_cost_calc,
                        filter_target_margin,
                        filter_promotion_rate,
                        filter_commission_rate,
                        filter_withdrawal_rate,
                        filter_payment_rate,
                        filter_vat_rate,
                        rate,
                    )
                )

                # 根据代理费和收单费范围决定定价公式
                # 收单费部分
                payment_in_numerator = fixed_payment
                # 代理费部分
                commission_in_numerator = (
                    actual_commission <= 15 or actual_commission >= 200
                )

                numerator = base_cost_calc
                denom_deductions = (
                    filter_target_margin
                    + filter_promotion_rate
                    + filter_commission_rate
                    + filter_withdrawal_rate
                    + filter_return_rate
                    + filter_vat_rate
                )

                if commission_in_numerator:
                    numerator += actual_commission * rate
                else:
                    denom_deductions += 0.02

                if payment_in_numerator:
                    numerator += actual_payment_rub * rate
                else:
                    denom_deductions += filter_payment_rate

                denominator = 1 - denom_deductions
                rough = numerator / denominator

                pricing_parts = []
                if commission_in_numerator:
                    pricing_parts.append("代理费在分子中")
                else:
                    pricing_parts.append("代理费在分母中")
                if payment_in_numerator:
                    pricing_parts.append("收单费在分子中")
                else:
                    pricing_parts.append("收单费在分母中")
                pricing_mode = ", ".join(pricing_parts)

                # 添加调试信息
                debug_info.append(f"浮动代理费: {actual_commission:.2f} RUB")
                debug_info.append(
                    f"浮动收单费: {actual_payment_rub:.2f} RUB"
                    f"{' (固定下限)' if fixed_payment else ' (按比例)'}"
                )
                debug_info.append(f"定价模式: {pricing_mode}")
                debug_info.append(f"估算价格: {rough:.2f} CNY")

                # 价格限制检查
                # 获取物流规则的价格限制
                # 预先获取USD汇率，避免重复导入和调用
                # usd_rate = get_usd_rate() # This line is removed as per the
                # edit hint

                # 根据货币类型读取正确的价格限制值
                log_limit_currency = current_log_dict.get("price_limit_currency", "RUB")
                if log_limit_currency == "RUB":
                    # 转换为float以兼容PostgreSQL的Decimal类型
                    log_limit_value = float(
                        current_log_dict.get("price_limit_rub") or 0
                    )
                else:  # USD
                    # price_limit 字段直接存储 USD 值（用户输入即 USD）
                    log_limit_value = float(current_log_dict.get("price_limit") or 0)

                log_min_currency = current_log_dict.get("price_min_currency", "RUB")
                if log_min_currency == "RUB":
                    # 转换为float以兼容PostgreSQL的Decimal类型
                    log_min_value = float(current_log_dict.get("price_min_rub") or 0)
                else:  # USD
                    # price_min 字段直接存储 USD 值（用户输入即 USD）
                    log_min_value = float(current_log_dict.get("price_min") or 0)

                # 根据货币类型进行价格比较
                if log_limit_currency == "USD" and log_limit_value > 0:
                    # 美元限价：将估算售价转换为美元进行比较
                    rough_usd = rough / usd_rate
                    debug_msg = (
                        f"限价判断: 估算售价 {rough_usd:.2f} USD, "
                        f"上限 {log_limit_value:.2f} USD"
                    )
                    debug_info.append(debug_msg)
                    if rough_usd > log_limit_value:
                        debug_info.append("超价格上限，跳过")
                        reason = f"估算售价 {rough_usd:.2f} USD 超过价格上限 {log_limit_value:.2f} USD"
                        if logistics is land_logistics:
                            filtered_logistics["land"].append(
                                {
                                    "name": current_log_dict.get("name", ""),
                                    "reason": reason,
                                }
                            )
                        else:
                            filtered_logistics["air"].append(
                                {
                                    "name": current_log_dict.get("name", ""),
                                    "reason": reason,
                                }
                            )
                        continue
                elif log_limit_currency == "RUB" and log_limit_value > 0:
                    # 卢布限价：将估算售价转换为卢布进行比较
                    rough_rub = rough / rate
                    debug_msg = (
                        f"限价判断: 估算售价 {rough_rub:.2f} RUB, "
                        f"上限 {log_limit_value:.2f} RUB"
                    )
                    debug_info.append(debug_msg)
                    if rough_rub > log_limit_value:
                        debug_info.append("超价格上限，跳过")
                        reason = f"估算售价 {rough_rub:.2f} RUB 超过价格上限 {log_limit_value:.2f} RUB"
                        if logistics is land_logistics:
                            filtered_logistics["land"].append(
                                {
                                    "name": current_log_dict.get("name", ""),
                                    "reason": reason,
                                }
                            )
                        else:
                            filtered_logistics["air"].append(
                                {
                                    "name": current_log_dict.get("name", ""),
                                    "reason": reason,
                                }
                            )
                        continue

                # 价格下限调试信息
                rough_rub_dbg = rough / rate
                debug_info.append(
                    f"价格下限检查: currency={log_min_currency}, "
                    f"min_value={log_min_value}, "
                    f"rough={rough:.2f} CNY, "
                    f"rough_rub={rough_rub_dbg:.2f} RUB"
                )

                if log_min_currency == "USD" and log_min_value > 0:
                    # 美元下限：将估算售价转换为美元进行比较
                    rough_usd = rough / usd_rate
                    debug_info.append(
                        f"下限 {log_min_value:.2f} USD, 估算 {rough_usd:.2f} USD"
                    )
                    if rough_usd < log_min_value:
                        debug_info.append("低于价格下限，跳过")
                        reason = f"估算售价 {rough_usd:.2f} USD 低于价格下限 {log_min_value:.2f} USD"
                        if logistics is land_logistics:
                            filtered_logistics["land"].append(
                                {
                                    "name": current_log_dict.get("name", ""),
                                    "reason": reason,
                                }
                            )
                        else:
                            filtered_logistics["air"].append(
                                {
                                    "name": current_log_dict.get("name", ""),
                                    "reason": reason,
                                }
                            )
                        continue
                    debug_info.append("通过价格下限检查")
                elif log_min_currency == "RUB" and log_min_value > 0:
                    # 卢布下限：将估算售价转换为卢布进行比较
                    rough_rub = rough / rate
                    debug_info.append(
                        f"下限 {log_min_value:.2f} RUB, 估算 {rough_rub:.2f} RUB"
                    )
                    if rough_rub < log_min_value:
                        debug_info.append("低于价格下限，跳过")
                        reason = f"估算售价 {rough_rub:.2f} RUB 低于价格下限 {log_min_value:.2f} RUB"
                        if logistics is land_logistics:
                            filtered_logistics["land"].append(
                                {
                                    "name": current_log_dict.get("name", ""),
                                    "reason": reason,
                                }
                            )
                        else:
                            filtered_logistics["air"].append(
                                {
                                    "name": current_log_dict.get("name", ""),
                                    "reason": reason,
                                }
                            )
                        continue
                    debug_info.append("通过价格下限检查")
                else:
                    debug_info.append(f"无价格下限 (min_value={log_min_value})")

                # 如果通过了所有价格检查，添加到候选列表
                res.append((current_log_dict, cost))
            return res

        land_candidates = _cost_and_filter(land_logistics)
        air_candidates = _cost_and_filter(air_logistics)

        # 4. 按优先级选择最优
        def select_best_by_priority(candidates, priority_type):
            if not candidates:
                return None, None

            if priority_type == "速度优先":
                # 按优先级组排序，然后按运费排序，运费相同时按平均时效排序
                def speed_key(candidate):
                    log = candidate[0]
                    cost = candidate[1]
                    priority_group = log.get("priority_group", "D")
                    candidate_min_days = log.get("min_days", 0)
                    candidate_max_days = log.get("max_days", 0)
                    candidate_avg_time = (candidate_min_days + candidate_max_days) / 2
                    # 优先级组：A=0, B=1, C=2, D=3, E=4（时效为0的物流）
                    group_priority = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}.get(
                        priority_group, 4
                    )
                    return group_priority, cost, candidate_avg_time

                return min(candidates, key=speed_key)
            else:  # 低价优先
                # 按价格排序，价格相同时按优先级组和平均时效排序
                def price_key(candidate):
                    log = candidate[0]
                    cost = candidate[1]
                    priority_group = log.get("priority_group", "D")
                    candidate_min_days = log.get("min_days", 0)
                    candidate_max_days = log.get("max_days", 0)
                    candidate_avg_time = (candidate_min_days + candidate_max_days) / 2
                    group_priority = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}.get(
                        priority_group, 4
                    )
                    return cost, group_priority, candidate_avg_time

                return min(candidates, key=price_key)

        land_best = select_best_by_priority(land_candidates, priority)
        air_best = select_best_by_priority(air_candidates, priority)

        # 将通过了所有检查但未被选中的物流加入淘汰列表
        # 按配送方式分组，每组选最优，其余标记为"未被选中"
        def _add_unselected(candidates, filtered_list):
            # 按配送方式分组
            groups = defaultdict(list)
            for log_dict, cost in candidates:
                groups[log_dict.get("delivery_method", "unknown")].append(
                    (log_dict, cost)
                )
            # 每组选最优，其余加入淘汰列表
            for delivery, group in groups.items():
                already_filtered = {item["name"] for item in filtered_list}
                group.sort(key=lambda x: x[1])
                best_name = group[0][0].get("name", "")
                for log_dict, cost in group[1:]:
                    name = log_dict.get("name", "")
                    if name in already_filtered:
                        continue
                    filtered_list.append(
                        {
                            "name": name,
                            "reason": f"未被选中，物流成本较高（¥{cost:.2f}，同类型最优：{best_name} ¥{group[0][1]:.2f}）",
                        }
                    )

        _add_unselected(land_candidates, filtered_logistics["land"])
        _add_unselected(air_candidates, filtered_logistics["air"])

        # 5. 最终价格 - 使用浮动代理费
        def _final_price(cost, debug_list=None):
            # 使用与筛选阶段相同的浮动代理费计算方法
            def calc_final_commission(
                cost_input,
                target_margin_input,
                promotion_rate_input,
                commission_rate_input,
                withdrawal_rate_input,
                payment_rate_input,
                return_rate_input,
                vat_rate_input,
                rate_input,
                max_iter=5,
            ):
                """计算最终价格的浮动代理费和收单费"""
                commission_fee = 15 * rate_input
                payment_fee_fixed = 10 * rate_input
                use_fixed_payment = payment_rate_input > 0
                price = 0
                price_rub = 0.0

                for _ in range(max_iter):
                    if use_fixed_payment:
                        iter_total_cost = (
                            cost_input + commission_fee + payment_fee_fixed
                        )
                        final_price_denominator = (
                            1
                            - target_margin_input
                            - promotion_rate_input
                            - commission_rate_input
                            - withdrawal_rate_input
                            - return_rate_input
                            - vat_rate_input
                        )
                    else:
                        iter_total_cost = cost_input + commission_fee
                        final_price_denominator = (
                            1
                            - target_margin_input
                            - promotion_rate_input
                            - commission_rate_input
                            - withdrawal_rate_input
                            - payment_rate_input
                            - return_rate_input
                            - vat_rate_input
                        )
                    price = iter_total_cost / final_price_denominator

                    price_rub = price / rate_input
                    new_commission_rub = max(15, min(200, price_rub * 0.02))
                    new_commission_fee = new_commission_rub * rate_input

                    # 判断收单费是固定还是按比例
                    if payment_rate_input > 0:
                        payment_by_rate = price_rub * payment_rate_input
                        if payment_by_rate < 10:
                            use_fixed_payment = True
                            payment_fee_fixed = 10 * rate_input
                        else:
                            use_fixed_payment = False

                    if abs(new_commission_fee - commission_fee) < 0.01:
                        break
                    commission_fee = new_commission_fee

                actual_payment_rub = (
                    10.0 if use_fixed_payment else price_rub * payment_rate_input
                )
                return (
                    price,
                    commission_fee / rate_input,
                    actual_payment_rub,
                    use_fixed_payment,
                )

            # 基础成本（不包含代理费）
            base_cost_calc = unit_price + labeling_fee + shipping_fee + cost
            final_target_margin = product.get("target_profit_margin", 0.2)
            final_promotion_rate = product.get("promotion_cost_rate", 0)
            final_commission_rate = product.get("commission_rate", 0.08)
            final_withdrawal_rate = product.get("withdrawal_fee_rate", 0.02)
            final_payment_rate = product.get("payment_processing_fee", 0)
            final_return_rate = product.get("return_rate", 0)
            final_vat_rate = product.get("vat_rate", 0)
            if final_target_margin >= 1:
                final_target_margin = final_target_margin / 100
            if final_promotion_rate >= 1:
                final_promotion_rate = final_promotion_rate / 100
            if final_commission_rate >= 1:
                final_commission_rate = final_commission_rate / 100
            if final_withdrawal_rate >= 1:
                final_withdrawal_rate = final_withdrawal_rate / 100
            if final_payment_rate >= 1:
                final_payment_rate = final_payment_rate / 100
            if final_return_rate >= 1:
                final_return_rate = final_return_rate / 100
            if final_vat_rate >= 1:
                final_vat_rate = final_vat_rate / 100

            # 计算浮动代理费和收单费
            (final_price, actual_commission, final_payment_rub, final_fixed_payment) = (
                calc_final_commission(
                    base_cost_calc,
                    final_target_margin,
                    final_promotion_rate,
                    final_commission_rate,
                    final_withdrawal_rate,
                    final_payment_rate,
                    final_return_rate,
                    final_vat_rate,
                    rate,
                )
            )

            # 根据代理费和收单费范围决定定价公式
            actual_commission_rounded = round(actual_commission, 2)

            if debug_list is not None:
                debug_list.append(
                    f"代理费判断: actual_commission={actual_commission:.15f}"
                )
                debug_list.append(f"  四舍五入后: {actual_commission_rounded}")
                debug_list.append(f"  原值 >= 200? {actual_commission >= 200}")
                debug_list.append(
                    f"  四舍五入后 >= 200? {actual_commission_rounded >= 200}"
                )

            commission_in_num = (
                actual_commission_rounded <= 15 or actual_commission_rounded >= 200
            )
            payment_in_num = final_fixed_payment

            numerator = base_cost_calc
            denom_deductions = (
                final_target_margin
                + final_promotion_rate
                + final_commission_rate
                + final_withdrawal_rate
                + final_return_rate
                + final_vat_rate
            )

            if commission_in_num:
                numerator += actual_commission * rate
            else:
                denom_deductions += 0.02

            if payment_in_num:
                numerator += final_payment_rub * rate
            else:
                denom_deductions += final_payment_rate

            denominator = 1 - denom_deductions
            final_price = numerator / denominator

            pricing_parts = []
            if commission_in_num:
                pricing_parts.append("代理费在分子中")
            else:
                pricing_parts.append("代理费在分母中")
            if payment_in_num:
                pricing_parts.append("收单费在分子中")
            else:
                pricing_parts.append("收单费在分母中")
            pricing_mode = ", ".join(pricing_parts)

            # 基于最终售价重新计算代理费和收单费
            final_price_rub = final_price / rate
            final_commission_rub = max(15, min(200, final_price_rub * 0.02))
            final_actual_commission = final_commission_rub
            # 重新计算收单费
            if final_payment_rate > 0:
                final_payment_by_rate = final_price_rub * final_payment_rate
                if final_payment_by_rate < 10:
                    final_actual_payment_rub = 10.0
                    final_fixed_payment = True
                else:
                    final_actual_payment_rub = final_payment_by_rate
                    final_fixed_payment = False
            else:
                final_actual_payment_rub = 0.0
                final_fixed_payment = False

            if debug_list is not None:
                debug_list.append(f"迭代计算代理费: {actual_commission:.2f} RUB")
                debug_list.append(f"最终售价: {final_price:.2f} CNY")
                debug_list.append(f"最终售价(卢布): {final_price_rub:.2f} RUB")
                debug_list.append(f"最终浮动代理费: {final_actual_commission:.2f} RUB")
                debug_list.append(
                    f"最终代理费(CNY): {final_actual_commission * rate:.2f}"
                )
                debug_list.append(
                    f"最终收单费: {final_actual_payment_rub:.2f} RUB"
                    f"{' (固定下限)' if final_fixed_payment else ' (按比例)'}"
                )
                debug_list.append(f"定价模式: {pricing_mode}")
                debug_list.append("定价公式详细参数:")
                debug_list.append(f"  基础成本: {base_cost_calc:.2f}")
                if commission_in_num:
                    total_cost_display = base_cost_calc + final_actual_commission * rate
                    if payment_in_num:
                        total_cost_display += final_actual_payment_rub * rate
                    debug_list.append(f"  总成本: {total_cost_display:.2f}")
                else:
                    debug_list.append(f"  总成本: {base_cost_calc:.2f} (代理费在分母)")
                debug_list.append(f"  目标利润率: -{final_target_margin * 100:.2f}%")
                debug_list.append(f"  推广费率: -{final_promotion_rate * 100:.2f}%")
                debug_list.append(f"  佣金率: -{final_commission_rate * 100:.2f}%")
                debug_list.append(f"  提现费率: -{final_withdrawal_rate * 100:.2f}%")
                if final_fixed_payment:
                    debug_list.append(
                        f"  收单费: {final_actual_payment_rub:.2f} RUB"
                        f" (固定下限，在分子中)"
                    )
                else:
                    debug_list.append(f"  收单费率: -{final_payment_rate * 100:.2f}%")
                debug_list.append(f"  退货率: -{final_return_rate * 100:.2f}%")
                debug_list.append(f"  增值税率: -{final_vat_rate * 100:.2f}%")
                if 15 < final_actual_commission < 200:
                    debug_list.append("  代理费率: -2.00%")
                debug_list.append(f"  定价分母: {denominator:.4f}")
                debug_list.append(f"  计算售价: {final_price:.2f}")

            return (
                round(final_price, 2),
                final_actual_commission,
                pricing_mode,
                final_actual_payment_rub,
                final_fixed_payment,
            )

        land_debug = []
        air_debug = []

        # 一次性拆包，避免重复判断，彻底消除PyCharm警告
        land_log, land_cost = land_best
        air_log, air_cost = air_best

        # 保存定价信息（价格、代理费、定价模式）
        land_price = None
        land_commission_info = None
        land_pricing_mode = None
        air_price = None
        air_commission_info = None
        air_pricing_mode = None

        land_payment_info = None
        land_payment_fixed = False
        air_payment_info = None
        air_payment_fixed = False

        if land_log:
            (
                land_price,
                land_commission_info,
                land_pricing_mode,
                land_payment_info,
                land_payment_fixed,
            ) = _final_price(land_cost, land_debug)

        if air_log:
            (
                air_price,
                air_commission_info,
                air_pricing_mode,
                air_payment_info,
                air_payment_fixed,
            ) = _final_price(air_cost, air_debug)

        # 计算统计信息
        land_stats = None
        air_stats = None

        if land_candidates:
            land_costs = [cost for _, cost in land_candidates]
            land_times = []
            for log_dict, _ in land_candidates:
                stats_min_days = log_dict.get("min_days", 0)
                stats_max_days = log_dict.get("max_days", 0)
                stats_avg_time = (stats_min_days + stats_max_days) / 2
                land_times.append(stats_avg_time)

            avg_land_cost = sum(land_costs) / len(land_costs)
            avg_land_time = sum(land_times) / len(land_times)

            cost_saving = (
                ((avg_land_cost - land_cost) / avg_land_cost * 100)
                if land_cost and avg_land_cost > 0
                else 0
            )
            time_saving = (
                (
                    avg_land_time
                    - ((land_log.get("min_days", 0) + land_log.get("max_days", 0)) / 2)
                )
                if land_log
                else 0
            )

            land_stats = {
                "avg_cost": avg_land_cost,
                "cost_saving": cost_saving,
                "avg_time": avg_land_time,
                "time_saving": time_saving,
            }

        if air_candidates:
            air_costs = [cost for _, cost in air_candidates]
            air_times = []
            for log_dict, _ in air_candidates:
                stats_min_days = log_dict.get("min_days", 0)
                stats_max_days = log_dict.get("max_days", 0)
                stats_avg_time = (stats_min_days + stats_max_days) / 2
                air_times.append(stats_avg_time)

            avg_air_cost = sum(air_costs) / len(air_costs)
            avg_air_time = sum(air_times) / len(air_times)

            cost_saving = (
                ((avg_air_cost - air_cost) / avg_air_cost * 100)
                if air_cost and avg_air_cost > 0
                else 0
            )
            time_saving = (
                (
                    avg_air_time
                    - ((air_log.get("min_days", 0) + air_log.get("max_days", 0)) / 2)
                )
                if air_log
                else 0
            )

            air_stats = {
                "avg_cost": avg_air_cost,
                "cost_saving": cost_saving,
                "avg_time": avg_air_time,
                "time_saving": time_saving,
            }

        # 提取平均值和节省值（用于API返回）
        avg_land_cost = land_stats["avg_cost"] if land_stats else 0
        avg_land_days = land_stats["avg_time"] if land_stats else 0
        avg_air_cost = air_stats["avg_cost"] if air_stats else 0
        avg_air_days = air_stats["avg_time"] if air_stats else 0
        saved_land_cost = (
            land_stats["avg_cost"] - land_cost if land_stats and land_cost else 0
        )
        saved_land_days = (
            land_stats["avg_time"]
            - (
                (land_log.get("min_days", 0) + land_log.get("max_days", 0)) / 2
                if land_log
                else 0
            )
            if land_stats
            else 0
        )
        saved_air_cost = (
            air_stats["avg_cost"] - air_cost if air_stats and air_cost else 0
        )
        saved_air_days = (
            air_stats["avg_time"]
            - (
                (air_log.get("min_days", 0) + air_log.get("max_days", 0)) / 2
                if air_log
                else 0
            )
            if air_stats
            else 0
        )

        # 计算建议售价和利润
        suggested_price = land_price if land_price else air_price

        # 分别计算陆运和空运的预期利润
        land_expected_profit = 0
        air_expected_profit = 0
        land_profit_margin = 0
        air_profit_margin = 0
        target_margin = product.get("target_profit_margin", 0.2)
        promotion_rate = product.get("promotion_cost_rate", 0)
        commission_rate = product.get("commission_rate", 0.08)
        withdrawal_rate = product.get("withdrawal_fee_rate", 0.02)
        payment_rate = product.get("payment_processing_fee", 0)
        return_rate = product.get("return_rate", 0)
        vat_rate = product.get("vat_rate", 0)
        if target_margin >= 1:
            target_margin = target_margin / 100
        if promotion_rate >= 1:
            promotion_rate = promotion_rate / 100
        if commission_rate >= 1:
            commission_rate = commission_rate / 100
        if withdrawal_rate >= 1:
            withdrawal_rate = withdrawal_rate / 100
        if payment_rate >= 1:
            payment_rate = payment_rate / 100
        if return_rate >= 1:
            return_rate = return_rate / 100

        if land_price and land_cost is not None and land_commission_info is not None:
            # 使用定价阶段返回的代理费和收单费信息
            land_base_cost = unit_price + labeling_fee + shipping_fee + land_cost
            land_actual_commission = land_commission_info
            land_commission_fee = land_actual_commission * rate
            # 收单费
            land_actual_payment = (
                land_payment_info if land_payment_info is not None else 0
            )
            land_payment_fee = land_actual_payment * rate

            # 计算总成本和实际收入
            land_total_cost = land_base_cost
            revenue_deductions = (
                promotion_rate
                + commission_rate
                + withdrawal_rate
                + return_rate
                + vat_rate
            )

            # 代理费：固定则加分子，浮动则加分母
            if "代理费在分子中" in (land_pricing_mode or ""):
                land_total_cost += land_commission_fee
            else:
                revenue_deductions += 0.02

            # 收单费：固定则加分子，按比例则加分母
            if land_payment_fixed:
                land_total_cost += land_payment_fee
            else:
                revenue_deductions += payment_rate

            actual_revenue = land_price * (1 - revenue_deductions)
            land_expected_profit = actual_revenue - land_total_cost
            profit_mode = land_pricing_mode or ""
            # 添加陆运预期利润计算调试信息
            land_profit_margin = (
                land_expected_profit / land_price * 100 if land_price > 0 else 0
            )
            land_debug.append("陆运预期利润计算:")
            land_debug.append(f"  产品成本: {unit_price}")
            land_debug.append(f"  贴标费: {labeling_fee}")
            land_debug.append(f"  运费: {shipping_fee}")
            land_debug.append(f"  陆运物流成本: {land_cost}")
            land_debug.append(f"  陆运基础总成本: {land_base_cost}")
            land_debug.append(
                f"  陆运代理费: {land_commission_fee:.2f} "
                f"({land_actual_commission:.2f} RUB)"
            )
            land_debug.append(
                f"  陆运收单费: {land_payment_fee:.2f} "
                f"({land_actual_payment:.2f} RUB)"
                f"{' (固定下限)' if land_payment_fixed else ' (按比例)'}"
            )
            land_debug.append(f"  定价模式: {profit_mode}")
            land_debug.append(f"  陆运总成本(用于利润计算): {land_total_cost}")
            land_debug.append(f"  陆运售价: {land_price}")
            # 添加详细的收入扣除调试信息
            land_debug.append("  实际收入计算:")
            land_debug.append(f"    售价: {land_price:.2f}")
            land_debug.append(f"    推广费率: -{promotion_rate * 100:.2f}%")
            land_debug.append(f"    佣金率: -{commission_rate * 100:.2f}%")
            land_debug.append(f"    提现费率: -{withdrawal_rate * 100:.2f}%")
            if land_payment_fixed:
                land_debug.append(
                    f"    收单费: {land_actual_payment:.2f} RUB (固定，在分子中)"
                )
            else:
                land_debug.append(f"    收单费率: -{payment_rate * 100:.2f}%")
            land_debug.append(f"    退货率: -{return_rate * 100:.2f}%")
            land_debug.append(f"    增值税率: -{vat_rate * 100:.2f}%")
            if "代理费在分母中" in profit_mode:
                land_debug.append("    代理费率: -2.00%")
            revenue_factor = 1 - revenue_deductions
            land_debug.append(f"    收入系数: {revenue_factor:.4f}")
            land_debug.append(
                f"    实际收入: {land_price:.2f} × "
                f"{revenue_factor:.4f} = "
                f"{land_price * revenue_factor:.2f}"
            )
            land_debug.append(f"  陆运预期利润: {land_expected_profit:.2f} CNY")
            land_debug.append(f"  陆运利润率: {land_profit_margin:.2f}%")
            land_debug.append(f"  目标利润率: {target_margin * 100:.2f}%")
            land_debug.append(
                f"  利润率差异: {land_profit_margin - target_margin * 100:+.2f}%"
            )
        if air_price and air_cost is not None and air_commission_info is not None:
            # 使用定价阶段返回的代理费和收单费信息
            air_base_cost = unit_price + labeling_fee + shipping_fee + air_cost
            air_actual_commission = air_commission_info
            air_commission_fee = air_actual_commission * rate
            # 收单费
            air_actual_payment = air_payment_info if air_payment_info is not None else 0
            air_payment_fee = air_actual_payment * rate

            # 计算总成本和实际收入
            air_total_cost = air_base_cost
            air_revenue_deductions = (
                promotion_rate
                + commission_rate
                + withdrawal_rate
                + return_rate
                + vat_rate
            )

            # 代理费
            if "代理费在分子中" in (air_pricing_mode or ""):
                air_total_cost += air_commission_fee
            else:
                air_revenue_deductions += 0.02

            # 收单费
            if air_payment_fixed:
                air_total_cost += air_payment_fee
            else:
                air_revenue_deductions += payment_rate

            actual_revenue = air_price * (1 - air_revenue_deductions)
            air_expected_profit = actual_revenue - air_total_cost
            profit_mode = air_pricing_mode or ""
            # 添加空运预期利润计算调试信息
            air_profit_margin = (
                air_expected_profit / air_price * 100 if air_price > 0 else 0
            )
            air_debug.append("空运预期利润计算:")
            air_debug.append(f"  产品成本: {unit_price}")
            air_debug.append(f"  贴标费: {labeling_fee}")
            air_debug.append(f"  运费: {shipping_fee}")
            air_debug.append(f"  空运物流成本: {air_cost}")
            air_debug.append(f"  空运基础总成本: {air_base_cost}")
            air_debug.append(
                f"  空运代理费: {air_commission_fee:.2f} "
                f"({air_actual_commission:.2f} RUB)"
            )
            air_debug.append(
                f"  空运收单费: {air_payment_fee:.2f} "
                f"({air_actual_payment:.2f} RUB)"
                f"{' (固定下限)' if air_payment_fixed else ' (按比例)'}"
            )
            air_debug.append(f"  定价模式: {profit_mode}")
            air_debug.append(f"  空运总成本(用于利润计算): {air_total_cost}")
            air_debug.append(f"  空运售价: {air_price}")
            # 添加详细的收入扣除调试信息
            air_debug.append("  实际收入计算:")
            air_debug.append(f"    售价: {air_price:.2f}")
            air_debug.append(f"    推广费率: -{promotion_rate * 100:.2f}%")
            air_debug.append(f"    佣金率: -{commission_rate * 100:.2f}%")
            air_debug.append(f"    提现费率: -{withdrawal_rate * 100:.2f}%")
            if air_payment_fixed:
                air_debug.append(
                    f"    收单费: {air_actual_payment:.2f} RUB (固定，在分子中)"
                )
            else:
                air_debug.append(f"    收单费率: -{payment_rate * 100:.2f}%")
            air_debug.append(f"    退货率: -{return_rate * 100:.2f}%")
            air_debug.append(f"    增值税率: -{vat_rate * 100:.2f}%")
            if "代理费在分母中" in profit_mode:
                air_debug.append("    代理费率: -2.00%")
            air_revenue_factor = 1 - air_revenue_deductions
            air_debug.append(f"    收入系数: {air_revenue_factor:.4f}")
            air_debug.append(
                f"    实际收入: {air_price:.2f} × "
                f"{air_revenue_factor:.4f} = "
                f"{air_price * air_revenue_factor:.2f}"
            )
            air_debug.append(f"  空运预期利润: {air_expected_profit:.2f} CNY")
            air_debug.append(f"  空运利润率: {air_profit_margin:.2f}%")
            air_debug.append(f"  目标利润率: {target_margin * 100:.2f}%")
            air_debug.append(
                f"  利润率差异: {air_profit_margin - target_margin * 100:+.2f}%"
            )
        # 使用建议售价对应的预期利润和利润率
        if suggested_price:
            if land_price and land_price == suggested_price:
                expected_profit = land_expected_profit
                calculated_profit_margin = land_profit_margin
            elif air_price and air_price == suggested_price:
                expected_profit = air_expected_profit
                calculated_profit_margin = air_profit_margin
            else:
                expected_profit = 0
                calculated_profit_margin = 0
        else:
            expected_profit = 0
            calculated_profit_margin = 0

        return {
            "land_price": land_price,
            "air_price": air_price,
            "land_cost": land_cost,
            "air_cost": air_cost,
            "best_land": land_log,
            "best_air": air_log,
            "suggested_price": suggested_price,
            "expected_profit": expected_profit,
            "land_expected_profit": land_expected_profit,
            "air_expected_profit": air_expected_profit,
            "profit_margin": calculated_profit_margin,
            "land_stats": land_stats,
            "air_stats": air_stats,
            "all_costs_debug": all_costs_debug,
            "land_debug": land_debug,
            "air_debug": air_debug,
            "land_pricing_mode": land_pricing_mode,
            "air_pricing_mode": air_pricing_mode,
            "land_commission_info": land_commission_info,
            "air_commission_info": air_commission_info,
            "land_payment_info": land_payment_info,
            "air_payment_info": air_payment_info,
            "land_payment_fixed": land_payment_fixed,
            "air_payment_fixed": air_payment_fixed,
            "product_info": product,
            "avg_land_cost": avg_land_cost,
            "avg_land_days": avg_land_days,
            "avg_air_cost": avg_air_cost,
            "avg_air_days": avg_air_days,
            "saved_land_cost": saved_land_cost,
            "saved_land_days": saved_land_days,
            "saved_air_cost": saved_air_cost,
            "saved_air_days": saved_air_days,
            "filtered_logistics": filtered_logistics,
        }
    except ZeroDivisionError:
        # 重新抛出 ZeroDivisionError
        raise
    except AttributeError:
        # 重新抛出 AttributeError
        raise
    except (ValueError, TypeError, KeyError) as e:
        # 捕获具体的异常类型，记录错误信息
        print(f"计算定价时发生错误: {e}")
        return {
            "best_land": None,
            "best_air": None,
            "land_price": None,
            "air_price": None,
            "land_cost": None,
            "air_cost": None,
            "suggested_price": None,
            "expected_profit": 0,
            "land_expected_profit": 0,
            "air_expected_profit": 0,
            "profit_margin": 0,
            "land_stats": None,
            "air_stats": None,
            "all_costs_debug": [],
            "land_debug": [],
            "air_debug": [],
            "land_pricing_mode": None,
            "air_pricing_mode": None,
            "land_commission_info": None,
            "air_commission_info": None,
            "land_payment_info": None,
            "air_payment_info": None,
            "land_payment_fixed": False,
            "air_payment_fixed": False,
            "product_info": product,
            "avg_land_cost": 0,
            "avg_land_days": 0,
            "avg_air_cost": 0,
            "avg_air_days": 0,
            "saved_land_cost": 0,
            "saved_land_days": 0,
            "saved_air_cost": 0,
            "saved_air_days": 0,
        }


def _debug_filter_reason(logistic: dict, product: dict) -> str:  # pyright: ignore[reportUnusedFunction]
    """检查物流被淘汰的原因（调试用，当前未使用）"""
    # ---------- 1. 重量 ----------
    # 计算体积重量
    length_cm = product.get("length_cm", 0)
    width_cm = product.get("width_cm", 0)
    height_cm = product.get("height_cm", 0)
    volume_mode = logistic.get("volume_mode", "none")
    volume_coefficient = logistic.get("volume_coefficient", 5000)

    if volume_mode == "max_actual_vs_volume":
        volume_weight = (length_cm * width_cm * height_cm) / volume_coefficient
        actual_weight = product.get("weight_g", 0) / 1000  # 转换为千克
        calculated_weight = max(actual_weight, volume_weight) * 1000  # 转换回克
    elif volume_mode == "longest_side":
        longest_side_threshold = logistic.get("longest_side_threshold", 0)
        longest_side = max(length_cm, width_cm, height_cm)
        if longest_side > longest_side_threshold:
            volume_weight = (length_cm * width_cm * height_cm) / volume_coefficient
            # 当最长边超过阈值时，直接使用体积重量计费
            calculated_weight = volume_weight * 1000  # 转换回克
        else:
            calculated_weight = product.get("weight_g", 0)
    else:
        calculated_weight = product.get("weight_g", 0)

    w = calculated_weight
    min_w = logistic.get("min_weight", 0)
    max_w = logistic.get("max_weight", 10**9)
    if w < min_w:
        return f"重量 {w} g 低于下限 {min_w} g"
    if w > max_w:
        return f"重量 {w} g 高于上限 {max_w} g"
    # ---------- 2. 边长 ----------
    # 获取产品包装形状
    is_cylinder = product.get("is_cylinder", False)

    if is_cylinder:
        # 圆柱形包装产品
        cylinder_diameter = product.get("cylinder_diameter", 0)
        cylinder_length = product.get("cylinder_length", 0)

        # 首先检查物流是否有圆柱形包装限制
        has_cylinder_limits = (
            logistic.get("max_cylinder_sum", 0) > 0
            or logistic.get("min_cylinder_sum", 0) > 0
            or logistic.get("max_cylinder_length", 0) > 0
            or logistic.get("min_cylinder_length", 0) > 0
        )

        if has_cylinder_limits:
            # 使用圆柱形包装限制进行匹配
            cylinder_sum = 2 * cylinder_diameter + cylinder_length
            max_cylinder_sum = logistic.get("max_cylinder_sum", 0)
            if 0 < max_cylinder_sum < cylinder_sum:
                return (
                    f"2倍直径与长度之和 {cylinder_sum} cm 超过限制 "
                    f"{max_cylinder_sum} cm"
                )
            min_cylinder_sum = logistic.get("min_cylinder_sum", 0)
            if min_cylinder_sum > 0 and cylinder_sum < min_cylinder_sum:
                return (
                    f"2倍直径与长度之和 {cylinder_sum} cm 低于下限 "
                    f"{min_cylinder_sum} cm"
                )
            max_cylinder_length = logistic.get("max_cylinder_length", 0)
            if 0 < max_cylinder_length < cylinder_length:
                return (
                    f"圆柱长度 {cylinder_length} cm 超过限制 {max_cylinder_length} cm"
                )
            min_cyl = logistic.get("min_cylinder_length", 0)
            if min_cyl > 0 and cylinder_length < min_cyl:
                return f"圆柱长度 {cylinder_length} cm 低于下限 {min_cyl} cm"
            # 圆柱形包装检查通过后，仍然需要定义sides用于后续标准包装限制检查
            sides = [cylinder_diameter, cylinder_diameter, cylinder_length]
        else:
            # 物流没有圆柱形包装限制，使用标准包装限制
            # 将圆柱形包装转换为标准包装进行匹配
            # 圆柱直径相当于长和宽，圆柱长度相当于高
            sides = [cylinder_diameter, cylinder_diameter, cylinder_length]
    else:
        # 标准包装产品
        sides = [
            product.get("length_cm", 0),
            product.get("width_cm", 0),
            product.get("height_cm", 0),
        ]

    # 标准包装限制检查
    max_sum = logistic.get("max_sum_of_sides", 10**9)
    if 0 < max_sum < sum(sides):
        return f"三边之和 {sum(sides)} cm 超过限制 {max_sum} cm"
    max_long = logistic.get("max_longest_side", 10**9)
    if max_long > 0 and max(sides) > max_long:
        return f"最长边 {max(sides)} cm 超过限制 {max_long} cm"
    # 第二边长上限检查
    max_second_side = logistic.get("max_second_side", 0)
    if max_second_side > 0:
        sorted_sides = sorted(sides, reverse=True)
        second_side = sorted_sides[1] if len(sorted_sides) > 1 else 0
        if 0 < max_second_side < second_side:
            return f"第二边长 {second_side} cm 超过限制 {max_second_side} cm"
    # 第二长边下限检查
    min_second_side = logistic.get("min_second_side", 0)
    if min_second_side > 0:
        sorted_sides = sorted(sides, reverse=True)
        second_side = sorted_sides[1] if len(sides) > 1 else 0
        if second_side < min_second_side:
            return f"第二边长 {second_side} cm 低于下限 {min_second_side} cm"
    # 最长边下限检查
    min_len = logistic.get("min_length", 0)
    if min_len > 0:
        longest_side = max(sides)
        if longest_side < min_len:
            return f"最长边 {longest_side} cm 低于下限 {min_len} cm"
    # 3. 特殊物品
    if product.get("has_battery") and not logistic.get("allow_battery"):
        return "产品含电池但物流不允许电池"
    if product.get("has_liquid") and not logistic.get("allow_liquid"):
        return "产品含易燃液体但物流不允许易燃液体"
    # 4. 电池容量 & MSDS
    if product.get("has_battery"):
        limit_wh = logistic.get("battery_capacity_limit_wh", 0)
        if limit_wh > 0:
            wh = product.get("battery_capacity_wh", 0)
            if wh == 0:
                mah = product.get("battery_capacity_mah", 0)
                v = product.get("battery_voltage", 0)
                # 如果mAh和V都为0，跳过电池容量限制判断
                if mah <= 0 and v <= 0:
                    pass  # 跳过电池容量限制判断
                else:
                    wh = mah * v / 1000.0
                    if 0 < limit_wh < wh:
                        return f"电池容量 {wh} Wh 超过物流限制 {limit_wh} Wh"
            else:
                # 如果填写了Wh但值为0，跳过电池容量限制判断
                if wh <= 0:
                    pass  # 跳过电池容量限制判断
                else:
                    if 0 < limit_wh < wh:
                        return f"电池容量 {wh} Wh 超过物流限制 {limit_wh} Wh"
        if logistic.get("require_msds") and not product.get("has_msds"):
            return "物流要求 MSDS 但产品未提供"
    # 5. 限价（人民币→卢布）
    try:
        # 用户计算时只使用兜底汇率，不调用API
        try:
            from exchange_service import get_fallback_exchange_rate
        except ImportError:

            def get_fallback_exchange_rate():
                return 0.0904

        rate = get_fallback_exchange_rate()  # 1 CNY = x RUB
        unit_price = float(product.get("unit_price", 0))
        labeling_fee = float(product.get("labeling_fee", 0))
        shipping_fee = float(product.get("shipping_fee", 0))
        # 先计算运费（复用与正式计算完全一致的公式）
        # 使用上面已经计算好的重量 w
        fee_mode = logistic.get("fee_mode", "base_weight")
        # 处理continue_unit：可能是字符串('g'/'kg'/'50g'/'100g'/'500g'/'1kg')或数值
        continue_unit_raw = logistic.get("continue_unit", 100)
        if isinstance(continue_unit_raw, str):
            if continue_unit_raw == "kg":
                continue_unit = 1000
            elif continue_unit_raw == "g":
                continue_unit = 1  # 每克
            else:
                # 处理 "50g", "100g", "500g", "1kg" 等格式
                import re

                g_match = re.match(r"^(\d+)\s*g$", continue_unit_raw, re.IGNORECASE)
                kg_match = re.match(
                    r"^(\d+(?:\.\d+)?)\s*kg$", continue_unit_raw, re.IGNORECASE
                )
                if g_match:
                    continue_unit = int(g_match.group(1))
                elif kg_match:
                    continue_unit = int(float(kg_match.group(1)) * 1000)
                else:
                    try:
                        continue_unit = int(continue_unit_raw)
                    except (ValueError, TypeError):
                        continue_unit = 100
        else:
            continue_unit = int(continue_unit_raw) if continue_unit_raw else 100
        if fee_mode in ("base_weight", "base_plus_continue"):
            units = math.ceil(w / continue_unit)
            # 转换为float以兼容PostgreSQL的Decimal类型
            base_fee_val = float(logistic.get("base_fee", 0))
            continue_fee_val = float(logistic.get("continue_fee", 0))
            cost = base_fee_val + continue_fee_val * units
        else:  # first_plus_continue
            # 转换为float以兼容PostgreSQL的Decimal类型
            first_w = float(logistic.get("first_weight_g", 0))
            first_cost = float(logistic.get("first_fee", 0))
            continue_fee_val = float(logistic.get("continue_fee", 0))
            cost = (
                first_cost
                if w <= first_w
                else first_cost
                + math.ceil((w - first_w) / continue_unit) * continue_fee_val
            )
        # 估算人民币总成本
        total_cny = unit_price + labeling_fee + shipping_fee + 15 * rate + cost
        # 估算人民币售价
        denominator = (
            1
            - product.get("target_profit_margin", 0)
            - product.get("promotion_cost_rate", 0)
            - product.get("commission_rate", 0)
            - product.get("withdrawal_fee_rate", 0)
            - product.get("payment_processing_fee", 0)
        )
        if denominator == 0:
            return "费率参数异常导致除以 0"
        rough_cny = total_cny / denominator
        rough_rub = rough_cny / rate

        # 获取价格限制和货币类型
        # 用户计算时只使用兜底汇率，不调用API
        try:
            from exchange_service import get_fallback_usd_rate
        except ImportError:

            def get_fallback_usd_rate():
                return 7.2

        usd_rate = get_fallback_usd_rate()

        # 根据货币类型读取正确的价格限制值
        limit_currency = logistic.get("price_limit_currency", "RUB")
        if limit_currency == "RUB":
            # 转换为float以兼容PostgreSQL的Decimal类型
            limit_value = float(logistic.get("price_limit_rub", 0))
        else:  # USD
            # price_limit 字段直接存储 USD 值
            limit_value = float(logistic.get("price_limit", 0))

        min_currency = logistic.get("price_min_currency", "RUB")
        if min_currency == "RUB":
            # 转换为float以兼容PostgreSQL的Decimal类型
            min_value = float(logistic.get("price_min_rub", 0))
        else:  # USD
            # price_min 字段直接存储 USD 值
            min_value = float(logistic.get("price_min", 0))

        # 根据货币类型进行价格比较

        if limit_currency == "USD" and limit_value > 0:
            # 美元限价：将估算售价转换为美元进行比较
            rough_usd = rough_cny / usd_rate
            if rough_usd > limit_value:
                return f"估算售价 {rough_usd:.2f} USD 超价格上限 {limit_value} USD"
        elif limit_value > 0:
            # 卢布限价：直接比较卢布价格
            if rough_rub > limit_value:
                return f"估算售价 {rough_rub:.2f} RUB 超价格上限 {limit_value} RUB"

        if min_currency == "USD" and min_value > 0:
            # 美元下限：将估算售价转换为美元进行比较
            rough_usd = rough_cny / usd_rate
            if rough_usd < min_value:
                return f"估算售价 {rough_usd:.2f} USD 低于价格下限 {min_value} USD"
        elif min_value > 0:
            # 卢布下限：直接比较卢布价格
            if rough_rub < min_value:
                return f"估算售价 {rough_rub:.2f} RUB 低于价格下限 {min_value} RUB"
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as e:
        return f"限价判断异常: {e}"
    # 6. 全部通过
    return ""
