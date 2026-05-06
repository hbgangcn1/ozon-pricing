## Context

`PlanManagementPage.jsx` 的套餐编辑表单（`PlanEditForm` 组件）中，"计算次数"（`calcLimit`）和"物流模板"（`logisticsTemplate`）是纯数值输入框。后端用 `-1` 表示"无限"，但用户需要手动输入 `-1`，不直观。

**约束**:
- 仅修改前端 `frontend/src/pages/PlanManagementPage.jsx`
- 后端已支持 `-1` 表示无限，API 无需变更
- 使用项目现有的 shadcn Switch 组件（`frontend/src/components/ui/switch.jsx`）

## Goals / Non-Goals

**Goals:**
- 为 `calcLimit` 和 `logisticsTemplate` 各增加"无限"Switch 开关
- 开启时隐藏输入框、值设为 `-1`；关闭时显示输入框、恢复具体数值
- 表单初始化时自动检测 `-1` 并开启开关

**Non-Goals:**
- 不修改后端 API 或数据库（`calc_limit: int`，`-1` = 无限，已有）
- 不修改 `PlanCard` 展示组件或 `SubscriptionPage`（已正确显示"无限"）
- 不添加新依赖

## Decisions

### D1: Switch 组件复用 — shadcn Switch

**选择**: 使用项目已有的 `frontend/src/components/ui/switch.jsx`（Radix UI Switch）。

**理由**: 项目统一使用 shadcn/ui 组件库，无需引入新依赖。Switch 语义明确，适合布尔切换。

### D2: 状态管理 — formData 内联检测

**选择**: 通过 `formData.calcLimit === -1` 直接判断 Switch 状态，无需额外 state。

**理由**: 
- `-1` 本身就是"无限"的语义标记，无需冗余 boolean state
- 切换为"无限"时设 `-1`，切换为"有限"时恢复 `_prevCalcLimit`（或默认值 `10`）
- 使用 `_prev*` 临时字段记住上次的有限值，提交时过滤掉

### D3: 提交时清理临时字段

**选择**: `handleSubmit` 中通过 `localPlanToApi` 映射时过滤 `_prev*` 前缀字段，不发送给后端。

**理由**: `_prevCalcLimit` / `_prevLogisticsTemplate` 仅用于前端 UI 状态恢复，后端不需要也不应接收。

## Risks / Trade-offs

**[R1] 用户切换为有限后无前值可恢复** → 使用默认值（calcLimit: 10, logisticsTemplate: 3）作为兜底，用户可随时修改。

**[R2] 表单初始化时 `-1` 检测** → 初始化 `_prevCalcLimit` 为合理默认值（10），避免首次切换为"有限"时出现空值。

## Open Questions

_(无)_
