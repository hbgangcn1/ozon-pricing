## ADDED Requirements

### Requirement: 精确模式佣金计算与快速模式一致
精确模式和快速模式的佣金计算逻辑 SHALL 使用相同的 `calc_final_commission` 函数，且两种模式下相同产品参数应产生相同的佣金结果。

#### Scenario: 相同产品在两种模式下佣金一致
- **WHEN** 使用相同产品参数分别在快速模式和精确模式下计算
- **THEN** 佣金金额 SHALL 相同（在浮点精度范围内）

### Requirement: 排查并修复佣金最低值异常
系统 SHALL 排查精确模式中佣金最低不低于约 5.31 CNY（≈ 15 RUB）的根因。如果根因是 `calc_final_commission` 中的 `max(15, ...)` 硬编码下限不合理，SHALL 修复为合理值或基于实际佣金率计算。

#### Scenario: 低价产品佣金可低于 5.31 CNY
- **WHEN** 产品售价很低，按 commission_rate 计算的佣金应低于 15 RUB
- **THEN** 计算结果中的佣金 SHALL 反映实际计算值，不被人为抬高到 15 RUB

#### Scenario: 佣金下限符合 Ozon 平台规则
- **WHEN** 佣金被计算
- **THEN** 佣金下限 SHALL 符合 Ozon 平台实际规则（如果平台确有下限，则保留；如果没有，则移除）
