## Why

上一轮 multi-feature-improvements-v2 实施后，5 个功能存在 Bug 或 UI 质量不达标：计算结果丢失了低价/速度优先区分；物流列表和公共物流池页面 UI 混乱；删除全部功能失败；产品导入仍然崩溃；精确模式佣金存在不合理的最低值下限。这些问题直接影响核心业务流程的可用性，需要立即修复。

## What Changes

- **修复计算结果优先级丢失**：精确模式的分组结果需要同时展示低价优先和速度优先两套方案，而非仅默认低价优先。后端 `calculateGrouped` 需调用两次（每种优先级各一次），前端分组 Tab 内需展示两种优先级结果。
- **物流列表 UI Polish**：重新设计物流规则卡片的操作按钮区域，解决转空运/转陆运按钮导致的布局拥挤问题。使用 DropdownMenu 或优化按钮排列。
- **公共物流池修复与 Polish**：修复"删除全部"功能（`delete_all` 函数事务问题）；重新设计查看详情 Dialog 布局；在页面标题旁显示物流方式总数。
- **产品导入崩溃修复**：修复 xlsx 文件中包含日期/特殊类型单元格时导致 JSON 序列化失败的问题，确保 preview_rows 中所有值都是 JSON 安全类型。
- **精确模式佣金下限修复**：`calc_final_commission` 中 `max(15, ...)` 硬编码的 15 RUB 最低佣金不合理，需要改为使用产品实际佣金率计算，或移除/降低此下限，使精确模式佣金计算与快速模式行为一致。

## Capabilities

### New Capabilities
- `pricing-dual-priority`: 分组计算结果同时展示低价优先和速度优先两套方案
- `logistics-ui-polish`: 物流列表和公共物流池页面 UI 优化
- `product-import-fix`: 产品批量导入序列化安全修复
- `commission-floor-fix`: 精确模式佣金最低值下限修复

### Modified Capabilities

## Impact

- **后端文件**：`api/routes/pricing.py`（grouped 端点双优先级）、`pricing/final_price.py`（佣金下限）、`pricing/floating_price.py`（佣金下限）、`api/routes/products.py`（序列化安全）、`db/logistics_pool.py`（delete_all 事务）
- **前端文件**：`PricingPage.jsx`（分组结果双优先级 UI）、`LogisticsPage.jsx`（操作按钮布局）、`LogisticsPoolPage.jsx`（删除修复 + 详情 Dialog + 总数显示）、`ProductImportPage.jsx`（错误处理增强）
- **API 契约变更**：`/api/pricing/calculate-grouped` 响应结构变更——每个分组键的值从单个结果对象变为 `{price_priority: {...}, speed_priority: {...}}` 双结果结构
