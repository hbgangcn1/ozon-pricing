## ADDED Requirements

### Requirement: 精准模式使用佣金类目费率替代产品固定佣金率
精准模式下，定价公式分母中的佣金扣除率 SHALL 使用`commission_category`表中按价格梯度和fulfillment_type查询的佣金类目费率，替代产品表的固定`commission_rate`字段。FBP标签页(fbp_ru, fbp_cis) SHALL 使用FBP费率(`fbp_tier*_rate`)，rFBS标签页 SHALL 使用rFBS费率(`rfbs_tier*_rate`)。

**注意**：Ozon平台代理费（`max(15, min(200, price_rub * 0.02))`）保持不变，不在本次修改范围内。

#### Scenario: FBP标签页使用FBP佣金类目费率
- **WHEN** 精准模式计算fbp_ru或fbp_cis标签页的物流定价
- **THEN** 定价分母中的佣金扣除率使用`commission_category`表的`fbp_tier*_rate`字段值

#### Scenario: rFBS标签页使用rFBS佣金类目费率
- **WHEN** 精准模式计算rfbs_*标签页的物流定价
- **THEN** 定价分母中的佣金扣除率使用`commission_category`表的`rfbs_tier*_rate`字段值

#### Scenario: 佣金费率按价格梯度区分
- **WHEN** 产品售价属于不同价格梯度(≤1500₽/≤5000₽/>5000₽)
- **THEN** 系统 MUST 使用对应梯度的佣金费率(tier1/tier2/tier3)

#### Scenario: 快速模式不受影响
- **WHEN** 使用快速模式计算
- **THEN** 定价分母中继续使用产品表的`commission_rate`字段，不使用佣金类目费率

#### Scenario: 无佣金类目时fallback
- **WHEN** 精准模式产品未关联佣金类目（`commission_category_id`为空）
- **THEN** 回退到使用产品表的`commission_rate`字段
