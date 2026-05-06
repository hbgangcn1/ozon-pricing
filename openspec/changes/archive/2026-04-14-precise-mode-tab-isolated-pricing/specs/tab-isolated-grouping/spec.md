## ADDED Requirements

### Requirement: 精准模式按标签页独立计算物流分组
精准模式下，`calculate_pricing_grouped()` SHALL 确保每个标签页(rfbs_ru, rfbs_KZ, rfbs_BY, rfbs_KGZ, rfbs_UZ, rfbs_GE, rfbs_AZ, fbp_ru, fbp_cis)内的物流A-E分组仅包含属于该标签页的物流。不同标签页的分组结果 MUST 完全独立，不存在跨标签页的物流混入。

#### Scenario: rFBS-俄罗斯标签页只包含rFBS俄罗斯物流
- **WHEN** 精准模式计算rfbs_ru标签页的物流分组
- **THEN** A-E各组仅包含fulfillment_type=rFBS且destination=俄罗斯的物流，不包含FBP或其他国家的物流

#### Scenario: FBP-仅俄罗斯标签页只包含FBP俄罗斯物流
- **WHEN** 精准模式计算fbp_ru标签页的物流分组
- **THEN** A-E各组仅包含fulfillment_type=FBP且destination=俄罗斯的物流，不包含rFBS或其他国家的物流

#### Scenario: FBP-俄+CIS标签页包含FBP多国物流
- **WHEN** 精准模式计算fbp_cis标签页的物流分组
- **THEN** A-E各组仅包含fulfillment_type=FBP且destination=俄罗斯+CIS国家的物流

#### Scenario: 快速模式不受影响
- **WHEN** 使用快速模式计算物流分组
- **THEN** 分组逻辑保持原有行为不变
