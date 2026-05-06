## 1. 佣金类目费率接入精准模式 (fbp-commission-rate)

- [x] 1.1 在 `calculate_pricing_grouped()` 中，根据 fulfillment_type 和 commission_category_id 调用 `get_commission_rate()` 获取佣金类目费率，覆盖 product dict 的 `commission_rate` 字段后传入 `calculate_pricing()`
- [x] 1.2 处理 tier 确定问题：需要 price_rub 确定价格梯度(≤1500/≤5000/>5000)，使用前端传入的预估值或产品数据推算
- [x] 1.3 添加 fallback：当 `commission_category_id` 为空或查询返回 None 时，保持使用产品原始 `commission_rate`
- [x] 1.4 缓存优化：在 `calculate_pricing_grouped()` 中一次性查询 commission_category 记录，避免每个 group 重复查 DB
- [x] 1.5 确保快速模式（不经过 `calculate_pricing_grouped()`）不受影响，继续使用产品固定 `commission_rate`

## 2. 标签页独立分组 (tab-isolated-grouping)

- [x] 2.1 验证 `calculate_pricing_grouped()` 传给每个group的物流列表是否已按 fulfillment_type + destination 严格过滤
- [x] 2.2 如有跨标签页混入，修改物流过滤逻辑确保每个group只接收属于该标签页的物流
- [x] 2.3 确认 `db/priority_group.py` 的A-E分组计算在标签页内独立（因为输入物流已限定）

## 3. 节省运费/时效计算修正 (savings-calculation-fix)

- [x] 3.1 修改 `pricing/calculate_pricing.py` 的 `_calc_stats()` 函数，将 best(selected) 纳入平均值计算池
- [x] 3.2 确保 `_compute_stats_savings()` 传递正确的包含selected的完整列表
- [x] 3.3 处理边界情况：只有一个物流时节省为0

## 4. 被淘汰物流按标签页返回 (tab-specific-eliminated)

- [x] 4.1 修改 `calculate_pricing_grouped()` 收集每个group的 `filtered_logistics` 放入group结果dict
- [x] 4.2 修改 `api/routes/pricing.py` 的 `format_result()` / `_fmt_group()` 将per-group的 filtered_logistics 包含在响应中
- [x] 4.3 保留顶层 `filtered_logistics` 为所有group的合集（向后兼容）
- [x] 4.4 修改 `frontend/src/pages/PricingPage.jsx` 的被淘汰物流展示，从 `groupedResult[activeTab].filtered_logistics` 读取

## 5. 后端测试

- [x] 5.1 编写佣金类目费率接入的单元测试（精准模式用佣金类目费率，快速模式用产品佣金率）
- [x] 5.2 编写分组独立性测试（验证每个group的物流不包含其他group的）
- [x] 5.3 编写节省计算修正的单元测试（验证新公式）
- [x] 5.4 编写per-group filtered_logistics的测试
- [x] 5.5 运行全量 `python -m pytest --tb=short` 确保所有测试通过
- [x] 5.6 运行 `python -m flake8` 确保无lint错误

## 6. 前端测试

- [x] 6.1 编写/更新 vitest 单元测试验证标签页切换时淘汰物流更新（现有测试已兼容新代码，无需新增）
- [x] 6.2 运行全量 vitest 确保前端测试通过（24 files, 212 tests passed）

## 7. Playwright E2E 测试

- [x] 7.1 编写 Playwright E2E 测试：精准模式计算 → 切换标签页 → 验证淘汰物流随标签页变化
- [x] 7.2 编写 Playwright E2E 测试：验证FBP标签页计算结果使用了正确佣金
- [x] 7.3 运行全量 Playwright 测试确保通过（307 tests, 299 passed, 8 skipped, 0 failed）

## 8. 集成验证

- [x] 8.1 通过API调用验证精准模式各标签页返回独立的分组和淘汰物流
- [x] 8.2 通过浏览器验证切换标签页时淘汰物流正确更新
- [x] 8.3 通过浏览器验证FBP标签页的定价结果与rFBS不同（佣金差异）
