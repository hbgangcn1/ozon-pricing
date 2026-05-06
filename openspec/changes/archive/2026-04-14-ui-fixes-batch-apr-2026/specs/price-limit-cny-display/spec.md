## ADDED Requirements

### Requirement: 公共物流池详情面板显示人民币限价
公共物流池的详情查看面板 SHALL 显示 `price_limit_cny` 和 `price_min_cny` 字段的值作为限价，而非旧的 `price_limit` 和 `price_min` 字段。

#### Scenario: 查看物流详情中的价格限制
- **WHEN** 用户在公共物流池页面点击某个物流方式的查看按钮
- **THEN** 详情面板的"价格限制"区域 MUST 显示 `price_limit_cny`（价格上限）和 `price_min_cny`（价格下限）的值
- **AND** 显示值 MUST 带有 "¥" 人民币货币符号前缀

#### Scenario: 限价字段为空或零
- **WHEN** 某物流方式的 `price_limit_cny` 或 `price_min_cny` 为 null/0
- **THEN** 详情面板 MUST 显示 "¥0" 或 "-" 而非空白
