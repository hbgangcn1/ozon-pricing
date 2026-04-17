"""
测试优化后的浮动代理费筛选策略
"""

from decimal import Decimal

from pricing import calculate_pricing


class TestOptimizedCommission:
    """测试优化后的浮动代理费筛选策略"""

    def test_floating_commission_convergence(self):
        """测试浮动代理费计算的收敛性"""
        # 创建一个高价产品，确保代理费会达到最高200卢布
        product = {
            "unit_price": Decimal("1000"),  # 高价产品
            "labeling_fee": Decimal("0"),
            "shipping_fee": Decimal("0"),
            "target_profit_margin": Decimal("0.1"),  # 低利润率
            "promotion_cost_rate": Decimal("0"),
            "commission_rate": Decimal("0.08"),
            "withdrawal_fee_rate": Decimal("0.02"),
            "payment_processing_fee": Decimal("0"),
        }

        # 创建多个物流规则，包含不同的价格限制
        logistics = [
            {
                "name": "cheap_logistic",
                "base_cost": Decimal("50"),
                "continue_cost": Decimal("0"),
                "first_weight": 1,
                "continue_weight": 0,
                "fee_mode": "base_plus",
                "price_limit_rub": Decimal("5000"),  # 较低限价
                "price_min_rub": Decimal("0"),
            },
            {
                "name": "expensive_logistic",
                "base_cost": Decimal("200"),
                "continue_cost": Decimal("0"),
                "first_weight": 1,
                "continue_weight": 0,
                "fee_mode": "base_plus",
                "price_limit_rub": Decimal("20000"),  # 较高限价
                "price_min_rub": Decimal("0"),
            },
        ]

        result = calculate_pricing(product, logistics, [], priority="price")

        # 验证结果
        assert result is not None
        assert "all_costs_debug" in result

        # 检查调试信息中是否包含浮动代理费信息
        debug_info_found = False
        for debug_item in result["all_costs_debug"]:
            if "debug" in debug_item:
                for debug_msg in debug_item["debug"]:
                    if "浮动代理费" in debug_msg:
                        debug_info_found = True
                        # 验证代理费在合理范围内
                        import re

                        match = re.search(r"浮动代理费: ([\d.]+) RUB", debug_msg)
                        if match:
                            commission = float(match.group(1))
                            assert 15 <= commission <= 200, (
                                f"代理费 {commission} 超出范围"
                            )
                        break
                if debug_info_found:
                    break

        assert debug_info_found, "应该找到浮动代理费调试信息"

    def test_commission_limit_impact(self):
        """测试代理费上限对筛选的影响"""
        # 创建一个中等价格产品
        product = {
            "unit_price": Decimal("500"),
            "labeling_fee": Decimal("0"),
            "shipping_fee": Decimal("0"),
            "target_profit_margin": Decimal("0.15"),
            "promotion_cost_rate": Decimal("0"),
            "commission_rate": Decimal("0.08"),
            "withdrawal_fee_rate": Decimal("0.02"),
            "payment_processing_fee": Decimal("0"),
        }

        # 创建物流规则，设置一个接近代理费上限的价格限制
        logistics = [
            {
                "name": "test_logistic",
                "base_cost": Decimal("100"),
                "continue_cost": Decimal("0"),
                "first_weight": 1,
                "continue_weight": 0,
                "fee_mode": "base_plus",
                "price_limit_rub": Decimal("15000"),  # 设置一个合理的限价
                "price_min_rub": Decimal("0"),
            }
        ]

        result = calculate_pricing(product, logistics, [], priority="price")

        # 验证结果
        assert result is not None
        assert result["land_cost"] is not None or result["air_cost"] is not None

        # 验证最终价格在合理范围内
        if result["suggested_price"]:
            assert result["suggested_price"] > 0, "建议价格应该大于0"

    def test_performance_optimization(self):
        """测试性能优化效果"""
        product = {
            "unit_price": Decimal("200"),
            "labeling_fee": Decimal("0"),
            "shipping_fee": Decimal("0"),
            "target_profit_margin": Decimal("0.2"),
            "promotion_cost_rate": Decimal("0"),
            "commission_rate": Decimal("0.08"),
            "withdrawal_fee_rate": Decimal("0.02"),
            "payment_processing_fee": Decimal("0"),
        }

        logistics = [
            {
                "name": "test_logistic",
                "base_cost": Decimal("80"),
                "continue_cost": Decimal("0"),
                "first_weight": 1,
                "continue_weight": 0,
                "fee_mode": "base_plus",
                "price_limit_rub": Decimal("10000"),
                "price_min_rub": Decimal("0"),
            }
        ]

        # 多次计算，验证性能稳定性
        import time

        start_time = time.time()

        for _ in range(10):
            result = calculate_pricing(product, logistics, [], priority="price")
            assert result is not None

        end_time = time.time()
        execution_time = end_time - start_time

        # 验证执行时间在合理范围内（每次计算应该很快）
        assert execution_time < 5.0, f"执行时间过长: {execution_time:.2f}秒"

        print(f"10次计算总耗时: {execution_time:.3f}秒")

    def test_commission_range_validation(self):
        """测试代理费范围验证"""
        # 测试不同价格区间的代理费计算
        test_cases = [
            {"unit_price": 50, "expected_min": 15},  # 低价产品，应该是最低15卢布
            {"unit_price": 500, "expected_min": 15},  # 中等价格，应该在15-200之间
            {"unit_price": 5000, "expected_max": 200},  # 高价产品，应该是最高200卢布
        ]

        for test_case in test_cases:
            product = {
                "unit_price": Decimal(str(test_case["unit_price"])),
                "labeling_fee": Decimal("0"),
                "shipping_fee": Decimal("0"),
                "target_profit_margin": Decimal("0.2"),
                "promotion_cost_rate": Decimal("0"),
                "commission_rate": Decimal("0.08"),
                "withdrawal_fee_rate": Decimal("0.02"),
                "payment_processing_fee": Decimal("0"),
            }

            logistics = [
                {
                    "name": "test_logistic",
                    "base_cost": Decimal("50"),
                    "continue_cost": Decimal("0"),
                    "first_weight": 1,
                    "continue_weight": 0,
                    "fee_mode": "base_plus",
                    "price_limit_rub": Decimal("100000"),
                    "price_min_rub": Decimal("0"),
                }
            ]

            result = calculate_pricing(product, logistics, [], priority="price")

            # 验证结果
            assert result is not None

            # 检查调试信息中的代理费
            commission_found = False
            for debug_item in result["all_costs_debug"]:
                if "debug" in debug_item:
                    for debug_msg in debug_item["debug"]:
                        if "浮动代理费" in debug_msg:
                            import re

                            match = re.search(r"浮动代理费: ([\d.]+) RUB", debug_msg)
                            if match:
                                commission = float(match.group(1))
                                commission_found = True

                                # 验证代理费范围
                                if "expected_min" in test_case:
                                    assert commission >= test_case["expected_min"], (
                                        f"代理费 {commission} 低于预期最小值 {test_case['expected_min']}"
                                    )
                                if "expected_max" in test_case:
                                    assert commission <= test_case["expected_max"], (
                                        f"代理费 {commission} 高于预期最大值 {test_case['expected_max']}"
                                    )

                                # 验证代理费在15-200范围内
                                assert 15 <= commission <= 200, (
                                    f"代理费 {commission} 超出有效范围"
                                )
                                break
                    if commission_found:
                        break

            assert commission_found, (
                f"未找到代理费信息，产品价格: {test_case['unit_price']}"
            )
