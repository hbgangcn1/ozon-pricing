# Pricing Decimal Fix Specification

## Summary

修复定价计算中的 Decimal/float 类型混合运算错误，确保 FBP 物流分组计算正确返回结果。

## ADDED Requirements

### Requirement: logistic_cost SHALL return Decimal type

`calculate_logistic_cost` 函数返回的 `cost` 值必须是 `Decimal` 类型，即使是处理来自数据库的 `float` 类型字段。

### Requirement: FBP logistics SHALL calculate correctly in grouped pricing

FBP 物流（fbp_ru、fbp_cis）在分组定价计算时必须正确返回结果，不再因为类型错误返回空结果。

#### Scenario: FBP-CIS group returns valid results
- **WHEN** user calculates pricing for FBP logistics in CIS countries (KZ, BY)
- **THEN** `fbp_cis` group SHALL return non-empty `price_priority` and `speed_priority` results
- **AND** `filtered_logistics` SHALL contain matched logistics

#### Scenario: FBP-RU group returns valid results
- **WHEN** user calculates pricing for FBP logistics in Russia only
- **THEN** `fbp_ru` group SHALL return non-empty `price_priority` and `speed_priority` results
- **AND** `filtered_logistics` SHALL contain matched logistics

#### Scenario: rFBS-CIS groups return valid results
- **WHEN** user calculates pricing for rFBS logistics in CIS countries (KZ, BY, KGZ, UZ, GE, AZ)
- **THEN** each `rfbs_{country}` group SHALL return non-empty results when logistics exist for that destination

### Requirement: cost_filter SHALL handle Decimal inputs correctly

`cost_filter.py` 中的 `base_cost_calc` 计算必须正确处理 `Decimal` 类型的 `unit_price`、`labeling_fee`、`shipping_fee` 与 `Decimal` 类型的 `cost` 相加。

#### Scenario: Mixed decimal calculation succeeds
- **WHEN** `cost_and_filter` is called with Decimal product fees and Decimal logistic cost
- **THEN** the calculation `unit_price + labeling_fee + shipping_fee + cost` SHALL complete without TypeError
