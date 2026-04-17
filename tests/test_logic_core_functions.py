from decimal import Decimal

import pricing as lg


def test_calculate_logistic_cost_basic():
    """测试基础物流成本计算"""
    land = {
        "name": "Test Land",
        "type": "land",
        "min_days": 5,
        "max_days": 10,
        "fee_mode": "base_plus_continue",
        "base_fee": Decimal("100.0"),
        "continue_unit": 500,
        "continue_fee": Decimal("50.0"),
        "max_weight": 2000,
        "max_sum_of_sides": 300,
        "max_longest_side": 150,
    }

    product = {
        "weight_g": 1000,
        "length_cm": 20,
        "width_cm": 15,
        "height_cm": 10,
    }

    cost, _ = lg.calculate_logistic_cost(land, product)
    assert cost is not None
    assert cost > 0


def test_calculate_logistic_cost_weight_limits():
    """测试重量限制"""
    land = {
        "name": "Weight Limited",
        "type": "land",
        "min_days": 1,
        "max_days": 1,
        "fee_mode": "base_plus_continue",
        "base_fee": Decimal("10.0"),
        "continue_unit": 100,
        "continue_fee": Decimal("5.0"),
        "max_weight": 500,  # 限制500g
        "max_sum_of_sides": 1000,
        "max_longest_side": 1000,
    }

    product = {
        "weight_g": 1000,  # 超重
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 10,
    }

    # 超重情况
    cost, _ = lg.calculate_logistic_cost(land, product)
    assert cost is None


def test_calculate_logistic_cost_dimension_limits():
    """测试尺寸限制"""
    land = {
        "name": "Dimension Limited",
        "type": "land",
        "min_days": 1,
        "max_days": 1,
        "fee_mode": "base_plus_continue",
        "base_fee": Decimal("10.0"),
        "continue_unit": 100,
        "continue_fee": Decimal("5.0"),
        "max_weight": 10000,
        "max_sum_of_sides": 100,  # 限制三边和
        "max_longest_side": 50,  # 限制最长边
    }

    product = {
        "weight_g": 100,
        "length_cm": 60,  # 最长边60cm
        "width_cm": 30,
        "height_cm": 20,
    }

    # 超尺寸情况
    cost, _ = lg.calculate_logistic_cost(land, product)
    assert cost is None


def test_calculate_logistic_cost_fee_modes():
    """测试不同计费模式"""
    # 首重续重模式
    land_first_continue = {
        "name": "First Continue",
        "type": "land",
        "min_days": 1,
        "max_days": 1,
        "fee_mode": "first_continue",
        "first_weight": 500,
        "first_fee": Decimal("20.0"),
        "continue_unit": 100,
        "continue_fee": Decimal("5.0"),
        "max_weight": 10000,
        "max_sum_of_sides": 1000,
        "max_longest_side": 1000,
    }

    product = {
        "weight_g": 800,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 10,
    }

    cost, _ = lg.calculate_logistic_cost(land_first_continue, product)
    assert cost is not None
    assert cost > 0

    # 基础续重模式
    land_base_continue = {
        "name": "Base Continue",
        "type": "land",
        "min_days": 1,
        "max_days": 1,
        "fee_mode": "base_plus_continue",
        "base_fee": Decimal("15.0"),
        "continue_unit": 100,
        "continue_fee": Decimal("3.0"),
        "max_weight": 10000,
        "max_sum_of_sides": 1000,
        "max_longest_side": 1000,
    }

    cost, _ = lg.calculate_logistic_cost(land_base_continue, product)
    assert cost is not None
    assert cost > 0


def test_calculate_pricing_basic():
    """测试基础定价计算"""
    product = {
        "unit_price": Decimal("100.0"),
        "labeling_fee": Decimal("5.0"),
        "shipping_fee": Decimal("10.0"),
        "promotion_cost_rate": Decimal("0.05"),
        "commission_rate": Decimal("0.1"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "payment_processing_fee": Decimal("0.02"),
        "target_profit_margin": Decimal("0.2"),
        "weight_g": 500,
        "length_cm": 20,
        "width_cm": 15,
        "height_cm": 10,
    }

    land = [
        {
            "name": "Test Land",
            "type": "land",
            "min_days": 5,
            "max_days": 10,
            "fee_mode": "base_plus_continue",
            "base_fee": Decimal("50.0"),
            "continue_unit": 500,
            "continue_fee": Decimal("25.0"),
            "max_weight": 2000,
            "max_sum_of_sides": 300,
            "max_longest_side": 150,
        }
    ]

    result = lg.calculate_pricing(product, land, [], "低价优先")
    assert result["best_land"] is not None
    assert "land_cost" in result
    assert "land_price" in result


def test_calculate_pricing_no_valid_land():
    """测试无有效物流方案的情况"""
    product = {
        "unit_price": Decimal("100.0"),
        "labeling_fee": Decimal("5.0"),
        "shipping_fee": Decimal("10.0"),
        "promotion_cost_rate": Decimal("0.05"),
        "commission_rate": Decimal("0.1"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "payment_processing_fee": Decimal("2.0"),
        "target_profit_margin": Decimal("0.2"),
        "weight_g": 5000,  # 超重
        "length_cm": 20,
        "width_cm": 15,
        "height_cm": 10,
    }

    land = [
        {
            "name": "Limited Land",
            "type": "land",
            "min_days": 5,
            "max_days": 10,
            "fee_mode": "base_plus_continue",
            "base_fee": Decimal("50.0"),
            "continue_unit": 500,
            "continue_fee": Decimal("25.0"),
            "max_weight": 1000,  # 限制1000g
            "max_sum_of_sides": 300,
            "max_longest_side": 150,
        }
    ]

    result = lg.calculate_pricing(product, land, [], "低价优先")
    assert result["best_land"] is None


def test_calculate_pricing_battery_restrictions():
    """测试电池限制"""
    product = {
        "unit_price": Decimal("100.0"),
        "labeling_fee": Decimal("5.0"),
        "shipping_fee": Decimal("10.0"),
        "promotion_cost_rate": Decimal("0.05"),
        "commission_rate": Decimal("0.1"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "payment_processing_fee": Decimal("2.0"),
        "target_profit_margin": Decimal("0.2"),
        "weight_g": 500,
        "length_cm": 20,
        "width_cm": 15,
        "height_cm": 10,
        "has_battery": True,  # 含电池
    }

    land = [
        {
            "name": "No Battery Land",
            "type": "land",
            "min_days": 5,
            "max_days": 10,
            "fee_mode": "base_plus_continue",
            "base_fee": Decimal("50.0"),
            "continue_unit": 500,
            "continue_fee": Decimal("25.0"),
            "max_weight": 2000,
            "max_sum_of_sides": 300,
            "max_longest_side": 150,
            "allow_battery": False,  # 限制电池
        }
    ]

    result = lg.calculate_pricing(product, land, [], "低价优先")
    assert result["best_land"] is None


def test_calculate_pricing_msds_restrictions():
    """测试MSDS限制"""
    product = {
        "unit_price": Decimal("100.0"),
        "labeling_fee": Decimal("5.0"),
        "shipping_fee": Decimal("10.0"),
        "promotion_cost_rate": Decimal("0.05"),
        "commission_rate": Decimal("0.1"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "payment_processing_fee": Decimal("2.0"),
        "target_profit_margin": Decimal("0.2"),
        "weight_g": 500,
        "length_cm": 20,
        "width_cm": 15,
        "height_cm": 10,
        "has_battery": True,  # 含电池
        "has_msds": False,  # 无MSDS
    }

    land = [
        {
            "name": "MSDS Required Land",
            "type": "land",
            "min_days": 5,
            "max_days": 10,
            "fee_mode": "base_plus_continue",
            "base_fee": Decimal("50.0"),
            "continue_unit": 500,
            "continue_fee": Decimal("25.0"),
            "max_weight": 2000,
            "max_sum_of_sides": 300,
            "max_longest_side": 150,
            "allow_battery": True,
            "require_msds": True,  # 要求MSDS
        }
    ]

    result = lg.calculate_pricing(product, land, [], "低价优先")
    assert result["best_land"] is None


def test_calculate_pricing_price_limits():
    """测试价格限制"""
    product = {
        "unit_price": Decimal("1000.0"),  # 高单价
        "labeling_fee": Decimal("5.0"),
        "shipping_fee": Decimal("10.0"),
        "promotion_cost_rate": Decimal("0.05"),
        "commission_rate": Decimal("0.1"),
        "withdrawal_fee_rate": Decimal("0.02"),
        "payment_processing_fee": Decimal("2.0"),
        "target_profit_margin": Decimal("0.2"),
        "weight_g": 500,
        "length_cm": 20,
        "width_cm": 15,
        "height_cm": 10,
    }

    land = [
        {
            "name": "Price Limited Land",
            "type": "land",
            "min_days": 5,
            "max_days": 10,
            "fee_mode": "base_plus_continue",
            "base_fee": Decimal("50.0"),
            "continue_unit": 500,
            "continue_fee": Decimal("25.0"),
            "max_weight": 2000,
            "max_sum_of_sides": 300,
            "max_longest_side": 150,
            "price_limit": Decimal("500.0"),  # 价格上限
            "price_limit_currency": "RUB",
        }
    ]

    result = lg.calculate_pricing(product, land, [], "低价优先")
    # 价格限制检查在calculate_pricing中实现，这里验证结果
    assert isinstance(result, dict)


def test_calculate_pricing_zero_division_protection():
    """测试除零保护"""
    product = {
        "unit_price": Decimal("0.0"),  # 零单价
        "labeling_fee": Decimal("0.0"),
        "shipping_fee": Decimal("0.0"),
        "promotion_cost_rate": Decimal("0.0"),
        "commission_rate": Decimal("0.0"),
        "withdrawal_fee_rate": Decimal("0.0"),
        "payment_processing_fee": Decimal("0.0"),
        "target_profit_margin": Decimal("0.0"),
        "weight_g": 100,  # 非零重量
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 10,
    }

    land = [
        {
            "name": "Test Land",
            "type": "land",
            "min_days": 5,
            "max_days": 10,
            "fee_mode": "base_plus_continue",
            "base_fee": Decimal("10.0"),
            "continue_unit": 100,  # 非零续重单位
            "continue_fee": Decimal("5.0"),
            "max_weight": 2000,
            "max_sum_of_sides": 300,
            "max_longest_side": 150,
        }
    ]

    # 应该不会抛出除零错误
    result = lg.calculate_pricing(product, land, [], "低价优先")
    assert isinstance(result, dict)


def test_calculate_logistic_cost_cylinder():
    """测试圆柱体包装"""
    land = {
        "name": "Cylinder Land",
        "type": "land",
        "min_days": 1,
        "max_days": 1,
        "fee_mode": "base_plus_continue",
        "base_fee": Decimal("10.0"),
        "continue_unit": 100,
        "continue_fee": Decimal("5.0"),
        "max_weight": 10000,
        "max_sum_of_sides": 1000,
        "max_longest_side": 1000,
        "max_cylinder_sum": 200,  # 圆柱体限制
    }

    product = {
        "weight_g": 500,
        "is_cylinder": True,
        "cylinder_diameter": 10,
        "cylinder_length": 50,
    }

    cost, _ = lg.calculate_logistic_cost(land, product)
    assert cost is not None
    assert cost > 0  # cost是浮点数


def test_calculate_logistic_cost_volume_weight():
    """测试体积重量计算"""
    land = {
        "name": "Volume Weight Land",
        "type": "land",
        "min_days": 1,
        "max_days": 1,
        "fee_mode": "base_plus_continue",
        "base_fee": Decimal("10.0"),
        "continue_unit": 100,
        "continue_fee": Decimal("5.0"),
        "max_weight": 10000,
        "max_sum_of_sides": 1000,
        "max_longest_side": 1000,
        "volume_mode": "max_actual_vs_volume",  # 体积重量模式
        "volume_coefficient": 5000,
    }

    product = {
        "weight_g": 100,  # 轻重量
        "length_cm": 50,  # 大体积
        "width_cm": 50,
        "height_cm": 50,
    }

    cost, _ = lg.calculate_logistic_cost(land, product)
    assert cost is not None
    assert cost > 0  # cost是浮点数


def test_calculate_logistic_cost_battery_capacity():
    """测试电池容量限制"""
    land = {
        "name": "Battery Capacity Land",
        "type": "land",
        "min_days": 1,
        "max_days": 1,
        "fee_mode": "base_plus_continue",
        "base_fee": Decimal("10.0"),
        "continue_unit": 100,
        "continue_fee": Decimal("5.0"),
        "max_weight": 10000,
        "max_sum_of_sides": 1000,
        "max_longest_side": 1000,
        "battery_capacity_limit_wh": 100,  # 电池容量限制
    }

    product = {
        "weight_g": 500,
        "length_cm": 10,
        "width_cm": 10,
        "height_cm": 10,
        "has_battery": True,
        "battery_capacity_wh": 150,  # 超容量
    }

    cost, _ = lg.calculate_logistic_cost(land, product)
    assert cost is None  # 应该被限制
