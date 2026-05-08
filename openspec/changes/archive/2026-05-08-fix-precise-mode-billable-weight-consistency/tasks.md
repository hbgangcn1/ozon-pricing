# Tasks: fix-precise-mode-billable-weight-consistency

## 1. 新建共享 helper 模块

- [x] 1.1 创建 `pricing/_weight.py`，定义 `_compute_billable_weight(logistic, sides, actual_weight) -> tuple[float, str, bool]`，返回 `(weight, label, triggered)`
- [x] 1.2 实现 4 种 `volume_mode` 分支：`none` / `longest_side` / `sum_of_sides` / `max_actual_vs_volume`
- [x] 1.3 加入 `volume_coefficient <= 0` 防御：退化为 `none` 模式 + WARNING 日志（用 `logger_config` 现有 logger，不新增依赖）
- [x] 1.4 helper 函数 ≤ 100 行；不接 `product` 参数（sides 由调用方传入，保持解耦）

## 2. 重构 `pricing/logistic_cost.py`

- [x] 2.1 在 `calculate_logistic_cost` 顶部 import `_compute_billable_weight`
- [x] 2.2 用 helper 替换原来的 `_calc_volume_weight` 调用，得到 `billable_weight, label, triggered`
- [x] 2.3 将 `min_weight` / `max_weight` 校验**从早退分支（行 282-294）移到 helper 之后**，统一基于 `billable_weight` 判定
- [x] 2.4 保留 `actual_weight == 0 → base_fee` 早退（不与本次混合）
- [x] 2.5 将 `_calc_volume_weight` 改为薄 wrapper：内部调 helper 后只返回 weight 数值，保持向后兼容（仅供旧测试/外部调用，新代码禁用）
- [x] 2.6 `_calc_fee` 公开签名保持不变

## 3. 重构 `pricing/filter.py`

- [x] 3.1 在 `_filter_check_weight`（行 25-60）import 并调用 helper，移除原有 `volume_mode` 分支重复代码
- [x] 3.2 基于 helper 输出的 `billable_weight` + `label` + `triggered` 拼接 reason 文案
- [x] 3.3 重量超限文案严格按 spec：`f"{label} {weight:.2f}g 超过上限 {max_weight:g}g"` / `f"{label} {weight:.2f}g 低于下限 {min_weight:g}g"`，其中 label 直接来自 helper（"实重" 或 "体积重"），禁止拼"计费重量"通用前缀，禁止加"（已触发）"修饰
- [x] 3.4 修改 `_debug_filter_reason`（行 215-231）兜底分支：`return ""` 改为 `return "未识别的淘汰原因"`

## 4. 防御性兜底 `pricing/cost_filter.py`

- [x] 4.1 在 `_process_one_logistic` 的 `cost is None` 分支（约行 84），当 `_debug_filter_reason` 返回空字符串时，写入 `reason = "未识别的淘汰原因"`

## 5. 前端兜底渲染

- [x] 5.1 修改 `frontend/src/pages/pricing/PricingResultPanel.jsx` 行 213：`{reason || ''}` 改为 `{reason || '未提供原因'}`

## 6. 测试用例

- [x] 6.1 在 `tests/test_logic_pricing.py` 新增 `TestComputeBillableWeight` 类：覆盖 4 种 volume_mode、`volume_coefficient<=0` 防御、`max` 模式两个方向（实重>体积重 / 体积重>实重）
- [x] 6.2 新增**契约测试** `test_filter_and_cost_billable_weight_consistent`：构造同一 logistic+product，断言 `_filter_check_weight` 内部计算的 billable_weight 与 `calculate_logistic_cost` 内部一致（精度 0.01g）
- [x] 6.3 新增**回归测试** `test_volume_weight_passes_min_weight_check`：actual=2000g + min_weight=2001 + max_actual_vs_volume → logistic 不被淘汰且 cost 非 None（直接复现本次 bug）
- [x] 6.4 新增 `test_filter_reason_never_empty`：遍历 `_debug_filter_reason` 所有分支断言返回值非空字符串
- [x] 6.5 新增 `test_max_weight_exceeded_reason_format`：覆盖 4 个场景：(a) 体积重超上限 → `"体积重 11730.00g 超过上限 10000g"`；(b) max 模式实重>体积重时实重超上限 → `"实重 50000.00g 超过上限 30000g"`；(c) 实重低于下限 → `"实重 500.00g 低于下限 1000g"`；(d) 体积重低于下限 → `"体积重 800.00g 低于下限 1000g"`

## 7. 静态检查

- [x] 7.1 `python -m flake8 pricing/_weight.py pricing/logistic_cost.py pricing/filter.py pricing/cost_filter.py` 通过
- [x] 7.2 PyCharm Pylance + Cursor Pyright 警报全部清零（重点检查 helper 的类型标注）
- [x] 7.3 确认 4 个改动文件均 < 500 行；helper 函数 < 100 行

## 8. 回归测试

- [x] 8.1 `python -m pytest tests/test_logic_pricing.py --tb=short` 全绿（默认 `-n 4 --dist=loadscope`）
- [x] 8.2 `python -m pytest --tb=short` 全量测试全绿，无新增 warning
- [x] 8.3 前端 `cd frontend; npm run build` 成功
- [x] 8.4 前端 `cd frontend; npm run test` 全绿

## 9. 端到端验证（agent 自验，不让用户操作）

- [x] 9.1 后台启动后端（按 AGENTS.md 模板，设置 `ALLOWED_ORIGINS` + `E2E_TEST=1`）
- [x] 9.2 用 admin 账号 API 登录拿 token，对 product_id=13948 触发精准模式定价
- [x] 9.3 断言响应中：(a) *Big 系列 logistic 至少有一条 cost 非 None（min_weight=2001 ≤ 11730）；(b) `filtered_logistics[*].reason` 全部非空字符串 — API 自验：land=362/air=43 filtered，0 空 reason，speed_priority.land=`RETS Kazakhstan Standard Big` cost=317.52 ✅
- [x] 9.4 用 Playwright MCP 打开 `/pricing` 页面，对 product 13948 跑精准模式，截图淘汰列表，肉眼确认 reason 列无空白 — UI 自验：通过"选择产品"下拉菜单选 13948 → 计算 → 展开淘汰列表 141 条，"未提供原因"=0，"实重"出现 28 次，"Big" 系列 57 次（含中标），截图 `.playwright-mcp/ui_pricing_13948_kill_reasons.png`
- [x] 9.5 关闭后端进程

## 10. 最终验证 + 部署

- [ ] 10.1 `openspec validate fix-precise-mode-billable-weight-consistency` 通过
- [ ] 10.2 git commit（消息引用 change 名）
- [ ] 10.3 `git push origin main`
- [ ] 10.4 按 AGENTS.md 部署三步法：SSH `git pull` → 后台启 `deploy.sh` → 30s 后 `tail /tmp/deploy.log` 看到 healthcheck 通过
- [ ] 10.5 公网验证：`Invoke-WebRequest https://www.cbprice.cn/api/exchange/rates` 返回 200
- [ ] 10.6 浏览器验证生产 product 13948 精准模式淘汰原因列正常显示
- [ ] 10.7 `openspec archive fix-precise-mode-billable-weight-consistency`（走 openspec-archive-change skill）
