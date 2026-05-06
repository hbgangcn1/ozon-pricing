## ADDED Requirements

### Requirement: 定价结果正确判断可用性
系统 SHALL 在 `format_result()` 中将 `suggested_price` 为 `None` 或结果字典为空时判定为不可用（`is_available=False`），而 `suggested_price=0` 时 SHALL 判定为可用（`is_available=True`）。

#### Scenario: suggested_price 为 0 时结果可用
- **WHEN** `calculate_pricing` 返回结果且 `suggested_price=0`
- **THEN** `format_result()` 返回 `is_available=True`，价格显示为 0

#### Scenario: suggested_price 为 None 时结果不可用
- **WHEN** `calculate_pricing` 返回结果且 `suggested_price=None`
- **THEN** `format_result()` 返回 `is_available=False`

#### Scenario: 结果字典为空时不可用
- **WHEN** `calculate_pricing` 返回空字典或 None
- **THEN** `format_result()` 返回 `is_available=False`

### Requirement: 精准模式前端结果渲染
前端 `PricingPage.jsx` 的 `renderResult` SHALL 在精准模式下正确渲染 grouped 计算结果。当某个分组（如 rfbs_ru）的 land 和 air 均为 `is_available=true` 时 SHALL 显示结果卡片。

#### Scenario: grouped 结果中有可用组合
- **WHEN** 精准模式计算完成且 rfbs_ru 分组的 land 结果 `is_available=true`
- **THEN** 前端显示该分组的陆运结果卡片，包含价格、物流名称、时效等信息

#### Scenario: grouped 结果中所有组合均不可用
- **WHEN** 精准模式计算完成但所有分组所有组合均 `is_available=false`
- **THEN** 前端显示"暂无可用结果"提示，并提示用户检查物流配置
