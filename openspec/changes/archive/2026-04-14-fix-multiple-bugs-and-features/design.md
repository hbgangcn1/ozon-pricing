## Context

物流定价系统（FastAPI + React/shadcn/ui）正在生产使用中，用户报告了7个功能缺陷和1个开发体验需求。系统已从 Streamlit 迁移至 FastAPI + React 架构，前端使用 shadcn/ui + Tailwind CSS（dark theme），后端使用 SQLAlchemy ORM + PostgreSQL。现有测试基础设施完善（984 后端 pytest + 169 前端 Vitest + Playwright E2E）。

当前问题涉及的技术栈：
- 定价模块：`pricing/` 独立模块 + `api/routes/pricing.py` API层
- Excel导入：`xlsx_import/` 解析器 + `api/routes/products.py` 和 `api/routes/logistics_pool.py`
- 前端：React 18 + shadcn/ui (Radix UI) + Tailwind CSS + Zustand

## Goals / Non-Goals

**Goals:**
- 修复精准模式定价结果不显示的问题
- 修复公共物流池"删除全部"405错误
- 修复FBP Excel导入Smart物流识别不全（3/18）
- 修复批量产品导入截断（10/184）
- 统一物流池详情弹窗样式至全站dark theme
- 排查并修复被淘汰物流中出现不存在物流名的问题
- 创建前后端联合开发启动脚本
- 为所有修复编写全面测试
- 解释"货币"字段的作用

**Non-Goals:**
- 不重构定价模块整体架构
- 不修改前端技术栈或组件库
- 不修改数据库schema
- 不添加新功能（仅修复现有缺陷）
- 不优化性能（除非修复过程中附带改善）

## Decisions

### D1: 精准模式定价结果修复方案

**问题根因**：`api/routes/pricing.py` 第141行 `format_result()` 使用 `not res.get("suggested_price")` 判断可用性。当 `suggested_price=0` 时，Python将0视为falsy，导致有效结果被标记为 `is_available=False`。

**方案**：将判断改为 `res.get("suggested_price") is None`，允许价格为0的结果正常显示。同时检查前端 `PricingPage.jsx` 的 `renderResult` 逻辑，确保在grouped结果中所有组合的 `is_available=false` 时有合理的回退显示。

**替代方案**：将0价格视为错误并过滤 — 但0价格可能是合法结果（如免费物流），不应过滤。

### D2: 删除全部405错误修复

**问题根因**：FastAPI路由注册顺序问题。`logistics_pool.py` 中 `@router.delete("/all")` 定义在 `@router.patch("/{pool_id}")` 之后（第116行 vs 第85行）。当 DELETE 请求到达 `/api/logistics-pool/all` 时，`/{pool_id}` 路由先匹配路径（`all` 作为字符串），但该路由只注册了 PATCH 方法而非 DELETE，导致405 Method Not Allowed。

**方案**：将 `@router.delete("/all")` 路由定义移到 `/{pool_id}` 相关路由之前，确保静态路径优先匹配。

**替代方案**：将端点改为 `@router.delete("")` 或 `@router.post("/delete-all")` — 但这改变了API语义，不如调整顺序简洁。

### D3: FBP Smart物流识别

**问题根因**：`xlsx_import/parsers/fbp.py` 第67行仅检查 column C（service列）是否包含 "smart"。需要检查实际 Excel 文件确认 Smart 物流在哪些列/行出现，以及是否存在合并单元格导致 carry 机制遗漏。

**方案**：
1. 先分析实际 Excel 文件 `FBP_List_of_services_5_03_26_1772704547.xlsx` 的数据结构
2. 扩展 Smart 检测逻辑：检查 column C (service) 和 column G (name) 列是否包含 "smart"
3. 修复 carry 机制可能导致的合并单元格值遗漏

### D4: 批量产品导入截断修复

**问题根因**：`api/routes/products.py` 第155行 `rows[1:11]` 硬编码只取前10行作为预览。前端 `ProductImportPage.jsx` 的 confirm 流程仅发送预览行数据到 confirm 端点。

**方案**：
1. preview 端点改为返回全部行数据（移除 `[1:11]` 限制），前端展示前10行作为预览，但存储全部数据
2. confirm 端点接收全部行数据
3. 添加分批处理逻辑防止大文件内存问题（但184行不大，暂不需要）
4. 前端preview页面仍显示前N行预览 + "共M条" 提示

**替代方案**：confirm时重新上传文件并在后端完整解析 — 实现更复杂，需要临时文件管理，不如直接传全量数据。

### D5: 物流详情弹窗样式统一

**方案**：使用 `/audit` + `/polish` impeccable skills 审计 `LogisticsPoolPage.jsx` 的 Dialog 组件，将硬编码的 slate 颜色替换为 shadcn/ui CSS变量（`hsl(var(--background))`、`hsl(var(--card))` 等），与 `globals.css` 中定义的 dark theme 保持一致。

### D6: 被淘汰物流中出现不存在的物流

**分析方向**：
1. "Tanais Standard Small" 可能是公共物流池中的数据，通过"添加到我的物流"后被删除但在计算缓存中残留
2. 可能是 `calculate_pricing` 使用了全部用户物流（包括 `is_active=0` 的）
3. 需要在运行时检查 `get_user_logistics` 查询是否正确过滤 `is_active=1`

**方案**：确认并修复物流数据来源，确保定价计算仅使用用户当前活跃物流。

### D7: 联合启动脚本

**方案**：创建 `start_dev.ps1`（PowerShell）和 `start_dev.bat`（CMD），使用后台进程同时启动 uvicorn（port 8003）和 vite dev server（port 3001）。PowerShell 使用 `Start-Process`，BAT 使用 `start /B`。

## Risks / Trade-offs

- **[产品导入全量返回可能导致大文件内存问题]** → 对于数百行的Excel影响极小；若未来需处理万行级别文件，可添加分页或流式处理
- **[FBP Smart检测修改可能影响其他非Smart物流的识别]** → 需先分析Excel确认Smart标注位置，修改后用实际文件回归测试
- **[删除全部路由顺序调整可能影响其他路由]** → FastAPI路由匹配是按注册顺序的，静态路径放前面是最佳实践，不会影响其他路由
- **[格式化结果判断逻辑变更影响所有定价模式]** → 需确保 `suggested_price=None`（真正无结果）和 `suggested_price=0`（合法零价格）的区分正确
