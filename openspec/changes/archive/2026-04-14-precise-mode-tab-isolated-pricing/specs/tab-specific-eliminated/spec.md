## ADDED Requirements

### Requirement: 被淘汰物流按标签页独立显示
每个标签页 SHALL 显示仅属于该标签页的被淘汰物流。切换标签页时，被淘汰物流列表 MUST 更新为当前标签页对应的淘汰结果。

#### Scenario: 切换标签页时淘汰物流更新
- **WHEN** 用户从rfbs_ru标签页切换到fbp_ru标签页
- **THEN** 被淘汰物流列表显示fbp_ru标签页计算出的淘汰物流，不显示rfbs_ru的淘汰物流

#### Scenario: 每个标签页的淘汰物流只包含该标签页属性的物流
- **WHEN** 显示rfbs_KZ标签页的被淘汰物流
- **THEN** 列表中仅包含fulfillment_type=rFBS且destination=KZ的被淘汰物流

#### Scenario: API返回per-group的filtered_logistics
- **WHEN** 精准模式API返回grouped result
- **THEN** 每个group对象 MUST 包含独立的`filtered_logistics`字段，格式为`{"land": [...], "air": [...]}`

#### Scenario: 向后兼容顶层filtered_logistics
- **WHEN** 精准模式API返回grouped result
- **THEN** 顶层 MUST 保留合并后的`filtered_logistics`字段，包含所有group的淘汰物流合集
