## Context

后端 `/api/subscriptions/current` 接口已在 `SubscriptionResponse` 中返回 `expired_at` 字段（Unix epoch 秒），但前端 `SubscriptionPage.jsx` 未读取和展示该字段。用户希望在"当前套餐"卡片中直观看到订阅到期时间。

## Goals / Non-Goals

**Goals:**
- 在"当前套餐"卡片中展示付费订阅（效率版、专业版）的到期时间
- 格式统一为 `yyyy-mm-dd hh:mm:ss`
- 保持免费版和管理员角色的现有"永久有效"展示不变

**Non-Goals:**
- 修改后端 API 或数据模型
- 修改订阅过期提醒逻辑
- 添加新的状态管理或全局 store 变更

## Decisions

**Decision 1: 仅在前端格式化展示，不修改后端**
- 后端已返回 `expired_at`（Unix epoch 秒），前端直接用 `new Date(expired_at * 1000)` 格式化
- Rationale: 最小改动原则，后端零风险

**Decision 2: 对缺失 `expired_at` 的情况隐藏该行**
- 免费版和管理员返回的 `expired_at` 为 `null`，此时不显示"到期时间"文字，保持现有"永久有效"Badge
- Rationale: 避免免费用户看到混乱信息

**Decision 3: 复用现有状态，不引入新 state**
- `currentPlan` state 已包含 `expired_at`，只需在 JSX 中读取并条件渲染
- Rationale: 减少复杂度，利用现有数据流

## Risks / Trade-offs

- **[Risk]** `expired_at` 为 Unix epoch 秒，部分浏览器/Node 环境可能产生时区差异  
  → **Mitigation**: 使用 `toLocaleString('zh-CN')` 或自定义格式化函数确保东八区展示

- **[Risk]** 用户从免费版升级到付费版后，`expired_at` 从 `null` 变为有值，UI 需正确切换  
  → **Mitigation**: 条件渲染基于 `currentPlan?.expired_at` 的真值判断，天然支持状态切换
