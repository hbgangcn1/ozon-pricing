## 1. 分组计算结果双优先级

- [x] 1.1 修改 `pricing/calculate_pricing.py` 的 `calculate_pricing_grouped`：对每个分组键调用两次 `_group()`（priority="低价优先" 和 priority="速度优先"），返回 `{key: {"price_priority": result, "speed_priority": result}}` 结构
- [x] 1.2 修改 `api/routes/pricing.py` 的 `calculate-grouped` 端点：适配新的双优先级响应结构（`convert_decimals` 需递归处理嵌套层级）
- [x] 1.3 修改 `PricingPage.jsx` 精确模式分组 Tab 渲染：每个 Tab 内展示"低价优先"和"速度优先"两个区域，各自包含陆运/空运结果卡片
- [x] 1.4 更新 `tests/test_routes_pricing.py` 中 `test_calculate_grouped_returns_normal_and_breakeven_results` 测试用例，适配新的双优先级响应结构

## 2. 物流列表 UI Polish

- [x] 2.1 在 `LogisticsPage.jsx` 中将编辑、删除、转空运/转陆运三个操作按钮替换为 shadcn DropdownMenu 组件（保留 Switch 在行内）
- [x] 2.2 使用 impeccable 设计技能对 `LogisticsPage.jsx` 整体布局进行 polish（按钮间距、卡片样式、响应式适配）

## 3. 公共物流池修复与 Polish

- [x] 3.1 排查并修复"删除全部"失败的根因：`delete_all()` 中 ORM 批量删除需添加 `execution_options(synchronize_session=False)`
- [x] 3.2 在 `LogisticsPoolPage.jsx` 页面标题旁添加物流方式总数显示（从 API 列表响应或单独接口获取 count）
- [x] 3.3 使用 impeccable 设计技能重新设计 `LogisticsPoolPage.jsx` 查看详情 Dialog 布局（字段分组、间距、标题层级、响应式适配）

## 4. 产品导入崩溃修复

- [x] 4.1 修改 `api/routes/products.py` 的 preview endpoint：在构建 preview_rows 时，将所有非基本类型值（datetime、Decimal 等）转为字符串，确保 JSON 序列化安全
- [ ] 4.2 使用 "定价与物流表不计抛.xlsx" 文件手动测试导入流程，验证 Step 1 → Step 2 过渡不再崩溃

## 5. 精确模式佣金下限排查与修复

- [x] 5.1 排查精确模式和快速模式的产品数据差异：两种模式都使用相同的代理费计算逻辑 (`max(15, min(200, price_rub * 0.02))`)，已确认一致
- [x] 5.2 排查 `pricing/final_price.py` 中 `calc_final_commission` 的 `max(15, ...)` 下限：确认 15 RUB 下限为 Ozon 平台真实规则（代理服务费最低 15 RUB，最高 200 RUB），保留不改
- [x] 5.3 同步检查 `pricing/floating_price.py` 中是否有类似的佣金下限逻辑：已确认 `calc_floating_price` line 48 有相同的 `max(15, min(200, ...))` 逻辑，两个模块一致

## 6. 测试与验证

- [x] 6.1 运行后端 `python -m pytest --tb=short` 确保全部通过
- [x] 6.2 运行 `python -m flake8` 确保无 lint 错误
- [x] 6.3 运行前端 `npm run test` 确保前端测试通过
