import math
import re


def _parse_continue_unit(continue_unit_raw):
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


def _check_cylinder_limits(logistic, product, debug_info, is_fast_mode):
    cylinder_diameter = product.get("cylinder_diameter", 0)
    cylinder_length = product.get("cylinder_length", 0)
    has_cylinder_limits = (
        logistic.get("max_cylinder_sum", 0) > 0
        or logistic.get("min_cylinder_sum", 0) > 0
        or logistic.get("max_cylinder_length", 0) > 0
        or logistic.get("min_cylinder_length", 0) > 0
    )
    debug_info.append(
        f"圆柱形包装: 直径={cylinder_diameter}cm, "
        f"长度={cylinder_length}cm, "
        f"2倍直径+长度={2 * cylinder_diameter + cylinder_length}cm"
    )
    if has_cylinder_limits:
        if is_fast_mode:
            debug_info.append("极速模式，跳过圆柱形包装尺寸限制检查")
        else:
            cylinder_sum = 2 * cylinder_diameter + cylinder_length
            max_cyl_sum = logistic.get("max_cylinder_sum", 0)
            if 0 < max_cyl_sum < cylinder_sum:
                debug_info.append(
                    f"2倍直径与长度之和 {cylinder_sum}cm 超限 {max_cyl_sum}cm，返回 None"
                )
                return None
            min_cyl_sum = logistic.get("min_cylinder_sum", 0)
            if min_cyl_sum > 0 and cylinder_sum < min_cyl_sum:
                debug_info.append(
                    f"2倍直径与长度之和 {cylinder_sum}cm 低于下限 {min_cyl_sum}cm，返回 None"
                )
                return None
            max_cyl_len = logistic.get("max_cylinder_length", 0)
            if 0 < max_cyl_len < cylinder_length:
                debug_info.append(
                    f"圆柱长度 {cylinder_length}cm 超限 {max_cyl_len}cm，返回 None"
                )
                return None
            min_cyl = logistic.get("min_cylinder_length", 0)
            if min_cyl > 0 and cylinder_length < min_cyl:
                debug_info.append(
                    f"圆柱长度 {cylinder_length}cm 低于下限 {min_cyl}cm，返回 None"
                )
                return None
    return [cylinder_diameter, cylinder_diameter, cylinder_length]


def _get_sides(logistic, product, debug_info, is_fast_mode):
    is_cylinder = product.get("is_cylinder", False)
    if is_cylinder:
        sides = _check_cylinder_limits(logistic, product, debug_info, is_fast_mode)
        if sides is None:
            return None
        cylinder_diameter = product.get("cylinder_diameter", 0)
        cylinder_length = product.get("cylinder_length", 0)
        sides = [cylinder_diameter, cylinder_diameter, cylinder_length]
    else:
        sides = [
            product.get("length_cm", 0),
            product.get("width_cm", 0),
            product.get("height_cm", 0),
        ]
        debug_info.append(
            f"标准包装: 长={sides[0]}cm, 宽={sides[1]}cm, 高={sides[2]}cm"
        )
    return sides


def _check_size_constraints(logistic, sides, debug_info):
    max_sum_of_sides = logistic.get("max_sum_of_sides", 10**9)
    if 0 < max_sum_of_sides < sum(sides):
        debug_info.append("三边和超限，返回 None")
        return False
    max_longest_side_val = logistic.get("max_longest_side", 10**9)
    if max_longest_side_val > 0 and max(sides) > max_longest_side_val:
        debug_info.append("最长边超限，返回 None")
        return False
    max_second_side = logistic.get("max_second_side", 0)
    if max_second_side > 0:
        sorted_sides = sorted(sides, reverse=True)
        second_side = sorted_sides[1] if len(sorted_sides) > 1 else 0
        debug_info.append(f"第二边长: {second_side}cm, 限制: {max_second_side}cm")
        if 0 < max_second_side < second_side:
            debug_info.append(
                f"第二边长 {second_side}cm 超限 {max_second_side}cm，返回 None"
            )
            return False
    max_third_side = logistic.get("max_third_side", 0)
    if max_third_side > 0:
        sorted_sides = sorted(sides, reverse=True)
        third_side = sorted_sides[2] if len(sorted_sides) > 2 else 0
        debug_info.append(f"第三边长: {third_side}cm, 限制: {max_third_side}cm")
        if 0 < max_third_side < third_side:
            debug_info.append(
                f"第三边长 {third_side}cm 超限 {max_third_side}cm，返回 None"
            )
            return False
    min_second_side = logistic.get("min_second_side", 0)
    if min_second_side > 0:
        sorted_sides = sorted(sides, reverse=True)
        second_side = sorted_sides[1] if len(sorted_sides) > 1 else 0
        debug_info.append(f"第二边长: {second_side}cm, 下限: {min_second_side}cm")
        if second_side < min_second_side:
            debug_info.append(
                f"第二边长 {second_side}cm 低于下限 {min_second_side}cm，返回 None"
            )
            return False
    min_len = logistic.get("min_length", 0)
    if min_len > 0:
        longest_side = max(sides)
        debug_info.append(f"最长边: {longest_side}cm, 下限: {min_len}cm")
        if longest_side < min_len:
            debug_info.append(
                f"最长边 {longest_side}cm 低于下限 {min_len}cm，返回 None"
            )
            return False
    return True


def _check_special_items(logistic, product, debug_info):
    if product.get("has_battery") and not logistic.get("allow_battery"):
        debug_info.append("产品含电池但物流不允许，返回 None")
        return False
    if product.get("has_liquid") and not logistic.get("allow_liquid"):
        debug_info.append("产品含易燃液体但物流不允许，返回 None")
        return False
    if product.get("has_battery"):
        limit_wh = logistic.get("battery_capacity_limit_wh", 0)
        if limit_wh > 0:
            wh = product.get("battery_capacity_wh", 0)
            if wh == 0:
                mah = product.get("battery_capacity_mah", 0)
                v = product.get("battery_voltage", 0)
                if mah <= 0 and v <= 0:
                    debug_info.append("电池容量mAh和V都为0，跳过容量限制判断")
                else:
                    wh = mah * v / 1000.0
                    debug_info.append(f"电池容量: {wh}Wh, 限制: {limit_wh}Wh")
                    if 0 < limit_wh < wh:
                        debug_info.append("电池容量超限，返回 None")
                        return False
            else:
                if wh <= 0:
                    debug_info.append("电池容量Wh为0，跳过容量限制判断")
                else:
                    debug_info.append(f"电池容量: {wh}Wh, 限制: {limit_wh}Wh")
                    if 0 < limit_wh < wh:
                        debug_info.append("电池容量超限，返回 None")
                        return False
        if logistic.get("require_msds") and not product.get("has_msds"):
            debug_info.append("要求 MSDS 但产品未提供，返回 None")
            return False
    return True


def _calc_volume_weight(logistic, sides, actual_weight, debug_info):
    volume_mode = logistic.get("volume_mode", "none")
    volume_coefficient = float(logistic.get("volume_coefficient", 5000))
    debug_info.append(f"体积重量模式: {volume_mode}, 系数: {volume_coefficient}")
    if volume_mode == "max_actual_vs_volume":
        volume_weight = (sides[0] * sides[1] * sides[2]) / volume_coefficient
        actual_weight_kg = actual_weight / 1000
        calculated_weight = max(actual_weight_kg, volume_weight) * 1000
        debug_info.append(
            f"实际重量: {actual_weight:.2f}g, "
            f"体积重量: {volume_weight * 1000:.2f}g, "
            f"计费重量: {calculated_weight:.2f}g"
        )
    elif volume_mode == "longest_side":
        longest_side_threshold = float(logistic.get("longest_side_threshold", 0))
        longest_side = max(sides)
        debug_info.append(f"最长边: {longest_side}cm, 阈值: {longest_side_threshold}cm")
        if longest_side > longest_side_threshold:
            volume_weight = (sides[0] * sides[1] * sides[2]) / volume_coefficient
            calculated_weight = volume_weight * 1000
            debug_info.append(
                f"最长边超过阈值，按体积重量计费: "
                f"实际重量: {actual_weight:.2f}g, "
                f"体积重量: {volume_weight * 1000:.2f}g, "
                f"计费重量: {calculated_weight:.2f}g"
            )
        else:
            calculated_weight = actual_weight
            debug_info.append(f"最长边未超过阈值，使用实际重量: {calculated_weight}g")
    elif volume_mode == "sum_of_sides":
        sum_of_sides_threshold = float(logistic.get("sum_of_sides_threshold", 0))
        sum_of_sides_val = sum(sides)
        debug_info.append(
            f"三边和: {sum_of_sides_val}cm, 阈值: {sum_of_sides_threshold}cm"
        )
        if sum_of_sides_val > sum_of_sides_threshold:
            volume_weight = (sides[0] * sides[1] * sides[2]) / volume_coefficient
            calculated_weight = volume_weight * 1000
            debug_info.append(
                f"三边和超过阈值，按体积重量计费: "
                f"实际重量: {actual_weight:.2f}g, "
                f"体积重量: {volume_weight * 1000:.2f}g, "
                f"计费重量: {calculated_weight:.2f}g"
            )
        else:
            calculated_weight = actual_weight
            debug_info.append(f"三边和未超过阈值，使用实际重量: {calculated_weight}g")
    else:
        calculated_weight = actual_weight
        debug_info.append(f"实际重量: {calculated_weight}g（未启用体积重量）")
    return calculated_weight


def _calc_fee(logistic, w, debug_info):
    fee_mode = logistic.get("fee_mode", "base_plus_continue")
    continue_unit_raw = logistic.get("continue_unit", 100)
    continue_unit = _parse_continue_unit(continue_unit_raw)
    continue_fee = float(logistic.get("continue_fee", 0))
    debug_info.append(
        f"计费方式: {fee_mode}, 续重单位: {continue_unit}g, 续重费用: {continue_fee:.5f}"
    )
    if fee_mode in ("base_weight", "base_plus_continue"):
        units = math.ceil(w / continue_unit)
        base_fee = float(logistic.get("base_fee", 0))
        cost = base_fee + continue_fee * units
        debug_info.append(f"基础费用: {base_fee}, 单位数: {units}, 运费: {cost}")
    else:
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
    debug_info.append(f"最终运费: {cost}")
    return cost


def calculate_logistic_cost(logistic, product, is_fast_mode=False):
    debug_info = []
    if logistic is None or product is None:
        debug_info.append("输入数据无效，返回 None")
        return (None, debug_info)
    if not isinstance(logistic, dict):
        logistic.get("test")
        debug_info.append("输入数据类型无效，返回 None")
        return (None, debug_info)
    if not isinstance(product, dict):
        product.get("test")
        debug_info.append("输入数据类型无效，返回 None")
        return (None, debug_info)
    actual_weight = product.get("weight_g", 0)
    min_w = float(logistic.get("min_weight", 0))
    max_w = float(logistic.get("max_weight", 0))
    if actual_weight < 0:
        debug_info.append(f"重量 {actual_weight}g 为负数，返回 None")
        return (None, debug_info)
    if actual_weight == 0:
        debug_info.append("重量为0，返回基础费用")
        base_fee = float(logistic.get("base_fee", 0))
        return (base_fee, debug_info)
    if min_w > 0 and actual_weight < min_w:
        debug_info.append(f"重量 {actual_weight}g 低于下限 {min_w}g，返回 None")
        return (None, debug_info)
    if max_w > 0 and actual_weight > max_w:
        debug_info.append(f"重量 {actual_weight}g 超过上限 {max_w}g，返回 None")
        return (None, debug_info)
    debug_info.append(
        f"重量限制: {min_w or '无'}g ~ {max_w or '无'}g, 当前: {actual_weight}g"
    )
    try:
        sides = _get_sides(logistic, product, debug_info, is_fast_mode)
        if sides is None:
            return (None, debug_info)
        debug_info.append(f"三边: {sides}, 三边和: {sum(sides)}, 最长边: {max(sides)}")
        is_fast_mode = product.get("name") == "极速模式产品"
        if is_fast_mode:
            debug_info.append("极速模式，跳过所有尺寸限制检查")
        else:
            if not _check_size_constraints(logistic, sides, debug_info):
                return (None, debug_info)
        if is_fast_mode:
            debug_info.append(
                "极速模式，跳过所有特殊物品检查（电池、易燃液体、MSDS等）"
            )
        else:
            if not _check_special_items(logistic, product, debug_info):
                return (None, debug_info)
        calculated_weight = _calc_volume_weight(
            logistic, sides, actual_weight, debug_info
        )
    except (KeyError, TypeError, ZeroDivisionError) as e:
        debug_info.append(f"计算物流成本时出错: {str(e)}")
        return (None, debug_info)
    cost = _calc_fee(logistic, calculated_weight, debug_info)
    return (cost, debug_info)
