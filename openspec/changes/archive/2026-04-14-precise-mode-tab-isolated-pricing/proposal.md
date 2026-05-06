## Why

精准模式的定价计算存在4个问题：1) 物流分组(A-E组)是跨所有标签页统一计算的，导致不同标签页看到的分组混入了不属于该标签页的物流；2) 定价公式分母中的`commission_rate`（佣金扣除率）始终使用产品表的固定值，未区分rFBS和FBP——精准模式应使用`commission_category`表中按价格梯度查询的佣金类目费率（FBP = rFBS - 1%）；3) 节省运费/时效的计算只对比viable candidates的平均值，不够全面；4) 被淘汰物流是全局共享的，切换标签页时显示不变。这些问题导致精准模式的计算结果不够准确、纯净。

**重要区分**：系统中存在三个不同的"佣金"概念：
- **佣金类目费率**（`commission_category`表）：按价格梯度(tier1/2/3)和fulfillment_type(rFBS/FBP)区分，用户在"佣金类目"页面配置。当前是死代码，本次需要接入精准模式。
- **产品佣金率**（`product.commission_rate`）：产品表的固定字段，在定价分母中使用。适合快速模式，精准模式需要用佣金类目费率替换。
- **代理费**（硬编码`price_rub * 0.02`）：Ozon平台浮动代理费`max(15, min(200, price_rub * 0.02))`，**本次不修改**。

## What Changes

- 精准模式下，物流A-E分组改为在每个标签页(rfbs_ru, rfbs_KZ, ..., fbp_ru, fbp_cis)内独立计算，不再跨标签页混合分组
- FBP标签页(fbp_ru, fbp_cis)使用`commission.py`中的`get_commission_rate()`查询FBP佣金费率，替代定价分母中产品级别的固定`commission_rate`；rFBS标签页使用rFBS费率
- 节省运费/时效改为将选中物流与"选中物流+所有候选物流总和的平均值"对比
- 每个标签页group返回独立的`filtered_logistics`（被淘汰物流），前端根据activeTab显示对应的淘汰物流
- 快速模式不做任何改动，保持原有逻辑

## Capabilities

### New Capabilities
- `tab-isolated-grouping`: 精准模式下按标签页(fulfillment_type+destination)独立计算物流A-E分组
- `fbp-commission-rate`: 精准模式使用佣金类目费率替代产品固定佣金率，区分rFBS/FBP
- `savings-calculation-fix`: 节省运费/时效计算公式修正为selected+candidates平均值对比
- `tab-specific-eliminated`: 被淘汰物流按标签页独立返回和显示

### Modified Capabilities

## Impact

- **后端核心文件**: `pricing/calculate_pricing.py`(分组逻辑、节省计算), `pricing/final_price.py`(佣金计算), `pricing/floating_price.py`(佣金计算), `api/routes/pricing.py`(API响应格式)
- **前端文件**: `frontend/src/pages/PricingPage.jsx`(标签页切换时显示对应淘汰物流)
- **数据库依赖**: `commission.py`的`get_commission_rate()`需要db_session，需在API层await获取费率后传入同步的计算函数
- **API响应格式**: grouped result中每个group增加`filtered_logistics`字段, **BREAKING** 对精准模式的响应结构有变化
- **测试影响**: 后端pytest + 前端vitest + Playwright E2E均需更新
