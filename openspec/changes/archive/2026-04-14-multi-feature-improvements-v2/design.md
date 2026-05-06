## Context

物流定价系统当前版本(v4.0.0)在生产使用中暴露了 8 类问题：UI 精度不合理、冗余字段、功能缺失、导入 bug、计算结果展示逻辑不佳等。系统采用 FastAPI + SQLAlchemy 2.0 后端，React + shadcn/ui + Zustand 前端，PostgreSQL 数据库，Alembic 迁移。

**当前约束：**
- 佣金表 `commission_category` 现存字段为 `fbp_tier1/2/3_rate`，需迁移到 `rfbs_tier1/2/3_rate`
- `calculate_pricing_grouped` 当前按 4 组分（rfbs_ru, rfbs_cis, fbp_ru, fbp_cis），CIS 不细分国家
- 物流池导入使用 `upsert`（按 source_file + delivery_method + destination 匹配），会覆盖已有数据
- `xlsx_import/detector.py` 格式检测仅通过 sheet title 关键词匹配，失败时只抛通用错误
- 前端计算结果页有独立的"价格优先"和"速度优先"区域，与分组结果分离

## Goals / Non-Goals

**Goals:**
- 修复所有 8 项用户反馈的问题，提升日常操作效率
- 物流规则编辑器价格精度限制为 2 位小数，隐藏不必要的电池容量字段
- 产品编辑器移除冗余的电池容量方式/Wh/mAh/V/MSDS 字段
- 公共物流池增加查看详情、删除全部功能，修复导入从覆盖改为追加
- 修复产品批量导入特定 xlsx 崩溃问题
- 佣金管理改为以 rFBS 为主，FBP 自动计算
- 计算结果页面合并优先方案到分组结果，CIS 国家细分，FBP 二次筛选
- 物流陆运/空运快速切换

**Non-Goals:**
- 不重构定价核心算法逻辑（`pricing/` 模块内部计算保持不变）
- 不新增用户角色或权限体系
- 不变更数据库引擎或 ORM 框架
- 不迁移前端组件库（保持 shadcn/ui）
- 不修改 JWT 认证/会话安全模块

## Decisions

### D1: 佣金字段迁移策略 — 新增 rfbs 字段 + Alembic 迁移

**选择**: 在 `commission_category` 表中新增 `rfbs_tier1/2/3_rate` 字段，通过 Alembic 迁移将已有的 `fbp_tier*_rate` 数据填充到 `rfbs_tier*_rate`（rfbs = fbp + 1%），后续 API 以 rfbs 为主字段，fbp 通过计算得出。保留旧字段兼容但标记 deprecated。

**替代方案**: 直接 rename 字段。**被排除因**为: rename 需要修改所有引用，且旧版 API 兼容性差；同时 Alembic rename + data migration 的事务复杂度更高。

**API 层变化**: `CategoryBody` schema 改为接收 `rfbs_tier1/2/3_rate`，返回中同时包含 rfbs 和 fbp（fbp = rfbs - 1%）。

### D2: 物流池导入 — 改为 INSERT + 错误详情

**选择**: 将 `logistics_pool.py` 的 `upsert` 调用改为新增的 `insert_row` 函数（纯 INSERT），保留历史数据累积。同时在 `detector.py` 中改进错误信息，返回可用的 sheet titles 列表帮助诊断。

**替代方案**: 保持 upsert 但加 dedup 逻辑。**被排除因**为: 用户明确要求"新增累积"，upsert 的 dedup 违反此语义。

### D3: 物流池删除全部 — DELETE /api/logistics-pool/all

**选择**: 新增 `DELETE /api/logistics-pool/all` endpoint，admin-only，执行 `DELETE FROM logistics_pool`。前端按钮需二次确认弹窗。

**替代方案**: 软删除（标记 is_active=0）。**被排除因**为: 用户要求"删除全部"是物理清空，软删不满足需求且会导致数据无限积累。

### D4: rFBS-CIS 国家细分 — 后端按国家分组计算

**选择**: 修改 `calculate_pricing_grouped`，将 `rfbs_cis` 拆分为 6 个国家级 key（`rfbs_KZ`, `rfbs_BY`, `rfbs_KGZ`, `rfbs_UZ`, `rfbs_GE`, `rfbs_AZ`）。前端用子 tab 展示。

**替代方案**: 前端根据 destination 字段过滤同一组结果。**被排除因**为: 不同国家可能有不同物流适用规则，后端分组计算更准确。

### D5: FBP-CIS 二次筛选 — 后端新增 post-processing 步骤

**选择**: 在 `calculate_pricing_grouped` 的 fbp_ru/fbp_cis 结果上增加二次筛选步骤：按 (fbp_company, fbp_service_level) 分组 → 每组取最高价候选 → 全部候选再做低价/速度优先排序。新增 `pricing/fbp_secondary_filter.py` 模块。

**替代方案**: 在前端做分组筛选。**被排除因**为: 筛选涉及业务逻辑（公司+service level 分组），属于后端职责。

### D6: 计算结果合并展示 — 前端重构

**选择**: 移除独立的"价格优先"和"速度优先"section，将 smart 推荐结果嵌入每个分组 tab 内部。每个结果卡片标题改为 `{物流名称} {Smart标志} {陆运/空运}`，移除"自提/送货上门"区分。

### D7: 物流陆运/空运切换 — PATCH endpoint + 前端按钮

**选择**: 新增 `PATCH /api/logistics/{id}/toggle-transport` endpoint，切换 `type` 字段（land ↔ air）。前端在物流列表每条记录上渲染条件按钮。

### D8: 产品批量导入崩溃修复 — 后端错误处理加固

**选择**: 在 `xlsx_import/detector.py` 和各 parser 中添加 try/except 包裹，返回结构化错误信息。前端 `ProductImportPage` 改进 error boundary 和错误展示。

## Risks / Trade-offs

**[R1] 佣金字段迁移数据丢失** → 迁移脚本先 `rfbs = fbp + 1%` 填充新字段，双写一段时间后再 deprecate 旧字段。Alembic downgrade 可回退。

**[R2] 物流池 INSERT 导致大量重复数据** → 用户已明确要求追加模式。如果后续需要去重，可单独提供合并工具。

**[R3] CIS 6 国家分组增加 API 响应体积** → 每个国家独立计算意味着 6x 计算量替代原来的 1x。可通过 lru_cache 和并行计算缓解。实际物流规则数量有限，性能影响可控。

**[R4] FBP 二次筛选逻辑可能筛掉最优结果** → 按规则每组取最高价是业务要求（保证 service level），不是 bug。需在前端明确展示筛选逻辑。

**[R5] 删除全部不可逆** → 通过二次确认弹窗 + 操作日志降低误操作风险。

## Migration Plan

1. **Alembic 迁移**：新增 `rfbs_tier1/2/3_rate` 字段到 `commission_category` 表
2. **数据迁移**：`UPDATE commission_category SET rfbs_tier1_rate = fbp_tier1_rate + 1, rfbs_tier2_rate = fbp_tier2_rate + 1, rfbs_tier3_rate = fbp_tier3_rate + 1`
3. **API 层更新**：修改 Pydantic schema，接收 rfbs，返回 rfbs + computed fbp
4. **前端更新**：佣金编辑弹窗改为 rFBS 输入，FBP 只读展示
5. **回退策略**：Alembic downgrade 可删除新字段，旧字段保持不变

## Open Questions

- 产品批量导入 `定价与物流表不计抛.xlsx` 的崩溃需要实际排查该文件结构，可能是 detector 无法识别或 parser 中某个字段缺失导致。需在实施阶段 debug 确认根因。
