## ADDED Requirements

### Requirement: 节省运费和时效计算使用全量平均值
节省运费和节省时效的计算 SHALL 使用"选中物流+所有候选物流"的总和平均值作为基准，而非仅使用候选物流的平均值。公式：avg = mean(selected_cost, candidate1_cost, candidate2_cost, ...)。节省金额 = avg - selected_cost。

#### Scenario: 节省运费包含选中物流在内的平均值
- **WHEN** 计算某个分组的节省运费
- **THEN** 平均运费 = (选中物流运费 + 所有候选物流运费之和) / (1 + 候选物流数量)
- **AND** 节省运费 = 平均运费 - 选中物流运费

#### Scenario: 节省时效包含选中物流在内的平均值
- **WHEN** 计算某个分组的节省时效
- **THEN** 平均时效 = (选中物流平均时效 + 所有候选物流平均时效之和) / (1 + 候选物流数量)
- **AND** 节省时效 = 平均时效 - 选中物流平均时效

#### Scenario: 只有一个物流时节省为零
- **WHEN** 某分组只有一个物流（既是selected也是唯一candidate）
- **THEN** 节省运费和节省时效均为0

#### Scenario: 快速模式不受影响
- **WHEN** 使用快速模式计算
- **THEN** 节省运费/时效计算保持原有逻辑
