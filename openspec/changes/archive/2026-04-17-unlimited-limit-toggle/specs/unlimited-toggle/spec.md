## ADDED Requirements

### Requirement: 计算次数支持无限开关

套餐编辑表单 SHALL 为"计算次数"（calcLimit）字段提供"无限"Switch 开关，开启时值设为 `-1` 并隐藏数值输入框，关闭时显示数值输入框供用户输入具体数值。

#### Scenario: 编辑已设为无限的套餐

- **WHEN** 用户编辑一个 `calcLimit === -1` 的套餐
- **THEN** "无限"开关显示为开启状态，数值输入框隐藏

#### Scenario: 切换为无限

- **WHEN** 用户将"无限"开关从关闭切换为开启
- **THEN** `calcLimit` 设为 `-1`，数值输入框隐藏

#### Scenario: 切换为有限

- **WHEN** 用户将"无限"开关从开启切换为关闭
- **THEN** `calcLimit` 恢复为上次的有限值（或默认值 `10`），数值输入框显示

### Requirement: 物流模板支持无限开关

套餐编辑表单 SHALL 为"物流模板"（logisticsTemplate）字段提供"无限"Switch 开关，行为与计算次数开关一致。

#### Scenario: 编辑已设为无限的套餐

- **WHEN** 用户编辑一个 `logisticsTemplate === -1` 的套餐
- **THEN** "无限"开关显示为开启状态，数值输入框隐藏

#### Scenario: 切换为无限

- **WHEN** 用户将"无限"开关从关闭切换为开启
- **THEN** `logisticsTemplate` 设为 `-1`，数值输入框隐藏

#### Scenario: 切换为有限

- **WHEN** 用户将"无限"开关从开启切换为关闭
- **THEN** `logisticsTemplate` 恢复为上次的有限值（或默认值 `3`），数值输入框显示

### Requirement: 提交时过滤临时字段

表单提交 SHALL 过滤 `_prev*` 前缀的临时字段，仅将 `calcLimit` 和 `logisticsTemplate` 的最终值（`-1` 或具体数值）发送给后端 API。

#### Scenario: 提交无限值套餐

- **WHEN** 用户提交一个两个字段均为"无限"的套餐
- **THEN** API 请求 payload 中 `calc_limit === -1` 且 `logistics_limit === -1`，不包含 `_prevCalcLimit` 或 `_prevLogisticsTemplate` 字段
