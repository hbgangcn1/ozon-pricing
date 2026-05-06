## Context

物流定价系统在上一轮 multi-feature-improvements-v2 中完成了 12 组 39 个任务。用户验收后发现 5 个问题：

1. **计算结果优先级丢失**：Group 8 将结果合并到分组 Tab 时，精确模式只调用一次 `calculate_pricing_grouped`（默认低价优先），丢失了速度优先方案。
2. **物流列表 UI 拥挤**：Group 11 添加的"转空运/转陆运"按钮与已有的编辑/删除按钮挤在 `flex gap-1` 中，导致视觉混乱。
3. **公共物流池三个问题**：(a) `delete_all` 使用 `flush()` 但 `get_db` 依赖在 yield 后 `commit()` —— 需确认是否有其他问题导致删除失败；(b) 查看详情 Dialog 布局混乱；(c) 需显示物流总数。
4. **产品导入崩溃**：xlsx 文件中的日期/特殊类型单元格在 preview_rows 中产生非 JSON 序列化类型（datetime 等），导致 FastAPI 响应序列化失败。
5. **精确模式佣金下限**：`calc_final_commission` 中 `max(15, min(200, price_rub * 0.02))` 硬编码 15 RUB 下限，换算为 CNY 约 5.31 元。此下限在快速模式中也存在，但快速模式产品数据可能不同导致最终结果差异。需排查精确模式独有的行为差异。

技术栈：FastAPI + SQLAlchemy 2.0 async + PostgreSQL | React 18 + shadcn/ui + Tailwind CSS + Zustand

## Goals / Non-Goals

**Goals:**
- 精确模式分组结果同时展示低价优先和速度优先两套方案
- 物流列表和公共物流池页面达到生产级 UI 质量
- 删除全部功能正常工作
- 产品导入不再因文件内容类型而崩溃
- 佣金计算在精确模式和快速模式中行为一致、合理

**Non-Goals:**
- 不重构定价引擎核心算法
- 不修改 `pricing/commission.py`（DB 佣金率查询保持不变）
- 不添加新功能，仅修复和 polish 已有功能

## Decisions

### D1: 双优先级 — 后端返回双结果 vs 前端调用两次

**选择**：后端 `calculate-grouped` 端点内部对每个分组键调用两次 `_group()`（低价优先 + 速度优先），返回 `{rfbs_ru: {price_priority: {...}, speed_priority: {...}}, ...}` 结构。

**理由**：减少前端网络请求（1 次 vs 2 次），保持前端逻辑简单。后端已有 `calculate_combo_results` 的双优先级模式可复用。

**替代方案**：前端调用两次 API — 增加延迟和复杂度，不选。

### D2: 物流列表操作按钮 — DropdownMenu vs 重排按钮

**选择**：将"转空运/转陆运"按钮改为操作下拉菜单（shadcn DropdownMenu），包含编辑、删除、转换运输方式三个选项。保留 Switch 在行内。

**理由**：当操作 > 3 个时，下拉菜单是标准做法，避免水平空间不足。

### D3: 公共物流池删除失败 — 排查 delete_all 事务

**选择**：先排查实际错误（可能是权限、路由匹配、或前端 API 路径问题），`get_db` 依赖在 yield 后已有 `commit()`，`flush()` 模式应该可以工作。需要实际测试确认根因。

### D4: 产品导入序列化 — 后端值转换

**选择**：在 `api/routes/products.py` 的 preview endpoint 中，将 preview_rows 中所有非基本类型值转为字符串。

**理由**：根源在后端，前端无法处理序列化失败的响应。

### D5: 佣金下限 — 排查精确模式独有行为

**选择**：先排查精确模式和快速模式的产品数据差异（DB 产品 vs 前端提交的 product_data），确认 `commission_rate` 字段是否不同。`max(15, ...)` 下限在两种模式中都存在，用户反馈"快速模式正常"可能是因为快速模式产品数据中的佣金率不同。需要通过日志或调试确认。

## Risks / Trade-offs

- **API 响应结构变更**：`calculate-grouped` 返回格式从 `{key: result}` 变为 `{key: {price_priority, speed_priority}}`，前端必须同步更新，否则完全不可用。→ 缓解：前后端在同一 PR 中同步修改。
- **佣金问题根因不确定**：5.31 元下限的根因可能不是 `max(15, ...)` 本身，而是精确模式的产品数据差异。→ 缓解：先排查确认，再决定修复方案。
- **UI Polish 主观性**：视觉优化是否"足够好"取决于用户感知。→ 缓解：使用 impeccable 设计技能确保一致性。
