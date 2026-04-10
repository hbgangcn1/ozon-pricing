from .final_price import compute_final_price
from .profit import calc_profit


def _compute_prices(
    land_best, air_best, product, unit_price, labeling_fee, shipping_fee, rate
):
    land_log, land_cost = land_best
    air_log, air_cost = air_best
    land_debug = []
    air_debug = []
    land_price = land_commission_info = land_pricing_mode = None
    air_price = air_commission_info = air_pricing_mode = None
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
        ) = compute_final_price(
            land_cost,
            product,
            unit_price,
            labeling_fee,
            shipping_fee,
            rate,
            land_debug,
        )
    if air_log:
        (
            air_price,
            air_commission_info,
            air_pricing_mode,
            air_payment_info,
            air_payment_fixed,
        ) = compute_final_price(
            air_cost,
            product,
            unit_price,
            labeling_fee,
            shipping_fee,
            rate,
            air_debug,
        )
    return (
        land_log,
        land_cost,
        land_price,
        land_commission_info,
        land_pricing_mode,
        land_payment_info,
        land_payment_fixed,
        land_debug,
        air_log,
        air_cost,
        air_price,
        air_commission_info,
        air_pricing_mode,
        air_payment_info,
        air_payment_fixed,
        air_debug,
    )


def _compute_profits(
    land_price,
    land_cost,
    land_commission_info,
    land_payment_info,
    land_payment_fixed,
    land_pricing_mode,
    land_debug,
    air_price,
    air_cost,
    air_commission_info,
    air_payment_info,
    air_payment_fixed,
    air_pricing_mode,
    air_debug,
    unit_price,
    labeling_fee,
    shipping_fee,
    rate,
    product,
):
    land_expected_profit = 0
    air_expected_profit = 0
    land_profit_margin = 0
    air_profit_margin = 0
    if land_price and land_cost is not None and land_commission_info is not None:
        land_expected_profit, land_profit_margin = calc_profit(
            land_price,
            land_cost,
            land_commission_info,
            land_payment_info,
            land_payment_fixed,
            land_pricing_mode,
            unit_price,
            labeling_fee,
            shipping_fee,
            rate,
            product,
            "陆运",
            land_debug,
        )
    if air_price and air_cost is not None and air_commission_info is not None:
        air_expected_profit, air_profit_margin = calc_profit(
            air_price,
            air_cost,
            air_commission_info,
            air_payment_info,
            air_payment_fixed,
            air_pricing_mode,
            unit_price,
            labeling_fee,
            shipping_fee,
            rate,
            product,
            "空运",
            air_debug,
        )
    return (
        land_expected_profit,
        land_profit_margin,
        air_expected_profit,
        air_profit_margin,
    )


def _pick_suggested(
    land_price,
    land_expected_profit,
    land_profit_margin,
    air_price,
    air_expected_profit,
    air_profit_margin,
):
    suggested_price = land_price if land_price else air_price
    if suggested_price:
        if land_price and land_price == suggested_price:
            return suggested_price, land_expected_profit, land_profit_margin
        elif air_price and air_price == suggested_price:
            return suggested_price, air_expected_profit, air_profit_margin
    return suggested_price, 0, 0


def _build_result(
    land_log,
    land_cost,
    land_price,
    land_commission_info,
    land_pricing_mode,
    land_payment_info,
    land_payment_fixed,
    land_debug,
    land_stats,
    air_log,
    air_cost,
    air_price,
    air_commission_info,
    air_pricing_mode,
    air_payment_info,
    air_payment_fixed,
    air_debug,
    air_stats,
    land_expected_profit,
    land_profit_margin,
    air_expected_profit,
    air_profit_margin,
    product,
    all_costs_debug,
    filtered_logistics,
    avg_land_cost,
    avg_land_days,
    saved_land_cost,
    saved_land_days,
    avg_air_cost,
    avg_air_days,
    saved_air_cost,
    saved_air_days,
):
    suggested_price, expected_profit, calculated_profit_margin = _pick_suggested(
        land_price,
        land_expected_profit,
        land_profit_margin,
        air_price,
        air_expected_profit,
        air_profit_margin,
    )
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
        "land_profit_margin": land_profit_margin,
        "air_profit_margin": air_profit_margin,
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
