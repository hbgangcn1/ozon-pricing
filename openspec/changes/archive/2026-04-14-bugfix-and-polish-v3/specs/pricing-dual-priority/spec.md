## ADDED Requirements

### Requirement: 分组计算结果包含双优先级方案
后端 `/api/pricing/calculate-grouped` 端点 SHALL 对每个分组键同时计算低价优先和速度优先两套结果。响应中每个分组键的值 SHALL 为 `{price_priority: <result>, speed_priority: <result>}` 结构，其中 `<result>` 保持与现有单结果格式完全一致。

#### Scenario: 分组计算返回双优先级结果
- **WHEN** 前端调用 `POST /api/pricing/calculate-grouped` 
- **THEN** 响应中每个键（如 `rfbs_ru`, `rfbs_KZ`, `fbp_ru` 等）的值 SHALL 包含 `price_priority` 和 `speed_priority` 两个子对象

#### Scenario: 每种优先级结果结构一致
- **WHEN** 响应中某个键的 `price_priority` 或 `speed_priority` 被解析
- **THEN** 其内部结构（`land_price`, `air_price`, `best_land`, `best_air`, `suggested_price` 等）SHALL 与现有单结果格式完全相同

### Requirement: 前端精确模式展示双优先级结果
前端精确模式的分组 Tab 内 SHALL 同时展示低价优先和速度优先两套方案，用户可以清晰区分。

#### Scenario: 精确模式分组 Tab 内显示双优先级
- **WHEN** 用户在精确模式下点击计算，查看任一分组 Tab（如 rFBS-俄罗斯）
- **THEN** Tab 内容 SHALL 包含"低价优先"和"速度优先"两个区域，各自展示对应的陆运/空运结果卡片

#### Scenario: 快速模式保持不变
- **WHEN** 用户在快速模式下点击计算
- **THEN** 结果展示 SHALL 与修改前完全相同（独立的 price_priority 和 speed_priority section）
