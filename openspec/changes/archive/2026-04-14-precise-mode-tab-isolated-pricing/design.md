## Context

精准模式的定价计算流程：`api/routes/pricing.py` → `pricing/calculate_pricing.py:calculate_pricing_grouped()` → 对每个fulfillment_type+destination组合调用 `calculate_pricing()` → `cost_filter.py:cost_and_filter()` → `final_price.py:compute_final_price()` → `select_best.py:select_best_by_priority()` → `_calc_stats()` 计算节省。

当前问题：
1. `db/priority_group.py` 的A-E分组在 `calculate_pricing_grouped()` 内部是否跨组——需要验证 `calculate_pricing()` 接收的物流列表是否已按标签页预过滤
2. 定价分母中的 `commission_rate` 来自 `product.commission_rate`（产品固定字段），精准模式不区分rFBS/FBP。需要用佣金类目费率替换。
3. `_calc_stats()` (102-126行) 用 `candidates`(通过过滤的物流) 算平均值
4. `filtered_logistics` 在 `calculate_pricing()` 第462行初始化为全局 `{"land": [], "air": []}`，`calculate_pricing_grouped()` 没有收集每个group的filtered_logistics

**重要：系统中三个不同的"佣金"概念**
- **佣金类目费率** (`commission_category`表): `rfbs_tier1/2/3_rate`, `fbp_tier1/2/3_rate`，按价格梯度区分。`get_commission_rate()`查询此表。**当前是死代码，本次需激活**。
- **产品佣金率** (`product.commission_rate`): 定价分母中 `1 - margin - promotion - commission_rate - ...`。精准模式需要用佣金类目费率替换此值。
- **代理费** (硬编码`0.02`): `max(15, min(200, price_rub * 0.02)` — Ozon平台浮动代理费。**不动**。

## Goals / Non-Goals

**Goals:**
- 精准模式每个标签页的物流分组(A-E)完全独立，不包含其他标签页的物流
- 精准模式使用佣金类目费率替代产品固定佣金率：FBP标签页用FBP费率，rFBS标签页用rFBS费率
- 节省运费/时效公式修正为：selected vs (selected + all_candidates) 的平均值
- 被淘汰物流按标签页独立返回和展示
- 所有测试（pytest + vitest + Playwright E2E）通过

**Non-Goals:**
- 不修改快速模式的任何逻辑（快速模式继续使用`product.commission_rate`）
- 不修改Ozon代理费（`price_rub * 0.02`）
- 不重构整体定价架构
- 不修改佣金类目管理界面
- 不改变API认证或权限模型

## Decisions

### D1: 佣金类目费率注入方式
**选择**: 在 `calculate_pricing_grouped()` 层面（async context）根据 fulfillment_type + price_rub + commission_category_id 调用 `get_commission_rate()` 获取佣金类目费率。将获取的费率注入到 product dict 的 `commission_rate` 字段中，覆盖产品原始值。这样下游的 `compute_final_price()` / `calc_floating_price()` / `cost_and_filter()` 无需任何签名改动。

**理由**: 
1. `get_commission_rate()` 是 async，需要 db_session。在 `calculate_pricing_grouped()`（已经是 async）中调用最自然。
2. 通过覆盖 product dict 的 `commission_rate` 字段，整条定价链路无需任何函数签名修改，影响面最小。
3. 快速模式不经过 `calculate_pricing_grouped()`，自然不受影响。

**替代方案**: 
- 给所有计算函数增加 `commission_rate` 参数 —— 拒绝，因为需要修改 6+ 个函数签名，改动面过大。
- 将 `compute_final_price()` 改为 async —— 拒绝，因为会导致整个计算链路都变 async。

### D2: 佣金费率需要price_rub来确定tier，但price_rub是计算结果
**选择**: 使用"初始估算 → 确定tier → 最终计算"的两步法。先用产品原始 `commission_rate` 做一次粗略估算得到 price_rub 范围，确定 tier，再用正确的佣金类目费率进行最终计算。或者更简单：直接在 API 层要求前端传入预估售价（前端已知产品信息），用它确定 tier。

**实际做法**: 观察到 `calculate_pricing_grouped()` 在调用 `calculate_pricing()` 之前并没有 price_rub。但 `get_commission_rate()` 接受的 price_rub 是用于确定 tier1/2/3 的阈值（≤1500, ≤5000, >5000）。可以：
- 方案A: 前端传入预估售价用于确定tier → 最简单
- 方案B: 使用产品的目标售价（如果有）确定tier
- 方案C: 先用中间tier(tier2)计算，然后迭代修正

**选择方案A**: 精准模式前端已经发送 `price_rub` 或可以从产品数据推算。如果没有，fallback到产品的 `commission_rate`。

### D3: 分组独立性实现
**选择**: 在 `calculate_pricing_grouped()` 中，确保传给每个group的 `calculate_pricing()` 的物流列表已经严格按 fulfillment_type + destination 过滤，使 `priority_group` 计算自然限定在标签页内。

**理由**: 如果 `calculate_pricing()` 接收的物流列表已经是标签页内的，那么 `cost_and_filter()` 和后续的分组逻辑自然只在这些物流中计算，无需修改 `priority_group.py`。

### D4: 节省计算公式修正
**选择**: 修改 `_calc_stats()` 的平均值计算，将 best (selected) 也纳入平均计算池：`avg = mean(selected_cost, *candidate_costs)`

**理由**: 用户明确要求 "选中的物流去对比选中的物流加上所有候选物流的总和的平均值"。

### D5: 被淘汰物流per-group返回
**选择**: 在 `calculate_pricing_grouped()` 中收集每个group调用 `calculate_pricing()` 返回的 `filtered_logistics`，放入该group的结果dict中。前端从 `groupedResult[activeTab].filtered_logistics` 读取。

**理由**: 最小改动。`calculate_pricing()` 已经返回 `filtered_logistics`，只需在 grouped 层面收集而非丢弃。

### D6: API响应格式变化
**选择**: grouped result 中每个 group 对象增加 `filtered_logistics` 字段。保持顶层 `filtered_logistics` 向后兼容（合并所有group的）。

**理由**: 前端按 activeTab 读取 group 级别的 filtered_logistics，但保留顶层字段避免破坏可能的外部调用者。

## Risks / Trade-offs

- **[佣金费率缓存]** `get_commission_rate()` 每次调用都查DB → 对精准模式（9个标签页×多组）可能有性能影响 → 在 `calculate_pricing_grouped()` 层面一次性查询 commission_category 记录，缓存后传递
- **[tier确定问题]** 佣金类目费率按price_rub分tier，但price_rub是计算输出 → 需要使用估算价格或前端传入的预估值确定tier → D2决策
- **[测试覆盖]** 佣金费率改动影响所有定价结果 → 需要确保测试fixtures包含commission_category数据 → 在conftest.py中添加fixture
- **[async传播]** `get_commission_rate()` 是 async，`calculate_pricing_grouped()` 已经是 async，但需在调用前resolve → 在grouped层await后注入product dict
