import math
import re


def _parse_continue_unit_filter(continue_unit_raw):
    if isinstance(continue_unit_raw, str):
        if continue_unit_raw == "kg":
            return 1000
        if continue_unit_raw == "g":
            return 1
        g_match = re.match(r"^(\d+)\s*g$", continue_unit_raw, re.IGNORECASE)
        kg_match = re.match(r"^(\d+(?:\.\d+)?)\s*kg$", continue_unit_raw, re.IGNORECASE)
        if g_match:
            return int(g_match.group(1))
        if kg_match:
            return int(float(kg_match.group(1)) * 1000)
        try:
            return int(continue_unit_raw)
        except (ValueError, TypeError):
            return 100
    return int(continue_unit_raw) if continue_unit_raw else 100


def _filter_check_weight(logistic, product):
    length_cm = product.get("length_cm", 0)
    width_cm = product.get("width_cm", 0)
    height_cm = product.get("height_cm", 0)
    volume_mode = logistic.get("volume_mode", "none")
    volume_coefficient = logistic.get("volume_coefficient", 5000)
    if volume_mode == "max_actual_vs_volume":
        volume_weight = (length_cm * width_cm * height_cm) / volume_coefficient
        actual_weight = product.get("weight_g", 0) / 1000
        calculated_weight = max(actual_weight, volume_weight) * 1000
    elif volume_mode == "longest_side":
        longest_side_threshold = logistic.get("longest_side_threshold", 0)
        longest_side = max(length_cm, width_cm, height_cm)
        if longest_side > longest_side_threshold:
            volume_weight = (length_cm * width_cm * height_cm) / volume_coefficient
            calculated_weight = volume_weight * 1000
        else:
            calculated_weight = product.get("weight_g", 0)
    elif volume_mode == "sum_of_sides":
        sum_of_sides_threshold = logistic.get("sum_of_sides_threshold", 0)
        sum_of_sides_val = length_cm + width_cm + height_cm
        if sum_of_sides_val > sum_of_sides_threshold:
            volume_weight = (length_cm * width_cm * height_cm) / volume_coefficient
            calculated_weight = volume_weight * 1000
        else:
            calculated_weight = product.get("weight_g", 0)
    else:
        calculated_weight = product.get("weight_g", 0)
    w = calculated_weight
    min_w = logistic.get("min_weight", 0)
    max_w = logistic.get("max_weight", 10**9)
    if w < min_w:
        return None, f"重量 {w} g 低于下限 {min_w} g"
    if w > max_w:
        return None, f"重量 {w} g 高于上限 {max_w} g"
    return w, None


def _filter_get_sides(logistic, product):
    is_cylinder = product.get("is_cylinder", False)
    if is_cylinder:
        cylinder_diameter = product.get("cylinder_diameter", 0)
        cylinder_length = product.get("cylinder_length", 0)
        has_cylinder_limits = (
            logistic.get("max_cylinder_sum", 0) > 0
            or logistic.get("min_cylinder_sum", 0) > 0
            or logistic.get("max_cylinder_length", 0) > 0
            or logistic.get("min_cylinder_length", 0) > 0
        )
        if has_cylinder_limits:
            cylinder_sum = 2 * cylinder_diameter + cylinder_length
            max_cyl_sum = logistic.get("max_cylinder_sum", 0)
            if 0 < max_cyl_sum < cylinder_sum:
                return None, (
                    f"2倍直径与长度之和 {cylinder_sum} cm 超过限制 {max_cyl_sum} cm"
                )
            min_cyl_sum = logistic.get("min_cylinder_sum", 0)
            if min_cyl_sum > 0 and cylinder_sum < min_cyl_sum:
                return None, (
                    f"2倍直径与长度之和 {cylinder_sum} cm 低于下限 {min_cyl_sum} cm"
                )
            max_cyl_len = logistic.get("max_cylinder_length", 0)
            if 0 < max_cyl_len < cylinder_length:
                return None, (
                    f"圆柱长度 {cylinder_length} cm 超过限制 {max_cyl_len} cm"
                )
            min_cyl = logistic.get("min_cylinder_length", 0)
            if min_cyl > 0 and cylinder_length < min_cyl:
                return None, f"圆柱长度 {cylinder_length} cm 低于下限 {min_cyl} cm"
        return [cylinder_diameter, cylinder_diameter, cylinder_length], None
    sides = [
        product.get("length_cm", 0),
        product.get("width_cm", 0),
        product.get("height_cm", 0),
    ]
    return sides, None


def _filter_check_sides(logistic, sides):
    max_sum = logistic.get("max_sum_of_sides", 10**9)
    if 0 < max_sum < sum(sides):
        return f"三边之和 {sum(sides)} cm 超过限制 {max_sum} cm"
    max_long = logistic.get("max_longest_side", 10**9)
    if max_long > 0 and max(sides) > max_long:
        return f"最长边 {max(sides)} cm 超过限制 {max_long} cm"
    max_second_side = logistic.get("max_second_side", 0)
    if max_second_side > 0:
        sorted_sides = sorted(sides, reverse=True)
        second_side = sorted_sides[1] if len(sorted_sides) > 1 else 0
        if 0 < max_second_side < second_side:
            return f"第二边长 {second_side} cm 超过限制 {max_second_side} cm"
    max_third_side = logistic.get("max_third_side", 0)
    if max_third_side > 0:
        sorted_s = sorted(sides, reverse=True)
        third_side = sorted_s[2] if len(sorted_s) > 2 else 0
        if 0 < max_third_side < third_side:
            return f"第三边长 {third_side} cm 超过限制 {max_third_side} cm"
    min_second_side = logistic.get("min_second_side", 0)
    if min_second_side > 0:
        sorted_sides = sorted(sides, reverse=True)
        second_side = sorted_sides[1] if len(sides) > 1 else 0
        if second_side < min_second_side:
            return f"第二边长 {second_side} cm 低于下限 {min_second_side} cm"
    min_len = logistic.get("min_length", 0)
    if min_len > 0:
        longest_side = max(sides)
        if longest_side < min_len:
            return f"最长边 {longest_side} cm 低于下限 {min_len} cm"
    return None


def _filter_check_special(logistic, product):
    if product.get("has_battery") and not logistic.get("allow_battery"):
        return "产品含电池但物流不允许电池"
    if product.get("has_liquid") and not logistic.get("allow_liquid"):
        return "产品含易燃液体但物流不允许易燃液体"
    if product.get("has_battery"):
        limit_wh = logistic.get("battery_capacity_limit_wh", 0)
        if limit_wh > 0:
            wh = product.get("battery_capacity_wh", 0)
            if wh == 0:
                mah = product.get("battery_capacity_mah", 0)
                v = product.get("battery_voltage", 0)
                if not (mah <= 0 and v <= 0):
                    wh = mah * v / 1000.0
                    if 0 < limit_wh < wh:
                        return f"电池容量 {wh} Wh 超过物流限制 {limit_wh} Wh"
            else:
                if wh > 0 and 0 < limit_wh < wh:
                    return f"电池容量 {wh} Wh 超过物流限制 {limit_wh} Wh"
        if logistic.get("require_msds") and not product.get("has_msds"):
            return "物流要求 MSDS 但产品未提供"
    return None


def _filter_calc_fee(logistic, w):
    fee_mode = logistic.get("fee_mode", "base_weight")
    continue_unit_raw = logistic.get("continue_unit", 100)
    continue_unit = _parse_continue_unit_filter(continue_unit_raw)
    if fee_mode in ("base_weight", "base_plus_continue"):
        units = math.ceil(w / continue_unit)
        base_fee_val = float(logistic.get("base_fee", 0))
        continue_fee_val = float(logistic.get("continue_fee", 0))
        return base_fee_val + continue_fee_val * units
    first_w = float(logistic.get("first_weight_g", 0))
    first_cost = float(logistic.get("first_fee", 0))
    continue_fee_val = float(logistic.get("continue_fee", 0))
    if w <= first_w:
        return first_cost
    return first_cost + math.ceil((w - first_w) / continue_unit) * continue_fee_val


def _filter_check_price_limits(logistic, product, w):
    try:
        try:
            from exchange_service import get_fallback_exchange_rate
        except ImportError:

            def get_fallback_exchange_rate():
                return 0.0904

        rate = get_fallback_exchange_rate()
        unit_price = float(product.get("unit_price", 0))
        labeling_fee = float(product.get("labeling_fee", 0))
        shipping_fee = float(product.get("shipping_fee", 0))
        cost = _filter_calc_fee(logistic, w)
        total_cny = unit_price + labeling_fee + shipping_fee + 15 * rate + cost
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
        limit_value = float(logistic.get("price_limit_cny", 0) or 0)
        min_value = float(logistic.get("price_min_cny", 0) or 0)
        if limit_value > 0 and rough_cny > limit_value:
            return f"估算售价 {rough_cny:.2f} CNY 超过价格上限 {limit_value:.2f} CNY"
        if min_value > 0 and rough_cny < min_value:
            return f"估算售价 {rough_cny:.2f} CNY 低于价格下限 {min_value:.2f} CNY"
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as e:
        return f"限价判断异常: {e}"
    return None


def _debug_filter_reason(logistic: dict, product: dict) -> str:
    w, err = _filter_check_weight(logistic, product)
    if err:
        return err
    sides, err = _filter_get_sides(logistic, product)
    if err:
        return err
    err = _filter_check_sides(logistic, sides)
    if err:
        return err
    err = _filter_check_special(logistic, product)
    if err:
        return err
    err = _filter_check_price_limits(logistic, product, w)
    if err:
        return err
    return ""
