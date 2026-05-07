## Context

`SubscriptionPage.jsx` 中的订阅计划卡片对企业版（`plan.code === 'enterprise'`）显示一个"联系客服升级"按钮（第243-250行）。实际上并没有客服升级流程，该按钮点击后无任何行为。需替换为"开发中……"文字。

当前代码结构：
```jsx
{plan.code === 'enterprise' ? (
  <Button className="w-full" disabled={plan.developing} variant={...}>
    联系客服升级
  </Button>
) : isCurrentPlan ? (
  // ...当前计划按钮
) : (
  // ...升级按钮
)}
```

## Goals / Non-Goals

**Goals:**
- 将企业版卡片底部的按钮替换为"开发中……"文字
- 保持卡片布局与其他计划卡片对齐一致

**Non-Goals:**
- 不涉及企业版定价、功能或后端逻辑
- 不涉及其他计划的按钮行为

## Decisions

**将 `<Button>` 替换为 `<span>` 或 `<div>` 文字**

理由：不再需要按钮交互，纯文字提示更准确地表达"不可操作"状态。使用与按钮相同容器高度的文字居中显示，保持视觉对齐。

替代方案：保留 `<Button disabled>` 并改文案 → 被拒绝，因为 disabled 按钮暗示功能存在但暂时不可用，而实际上功能尚不存在。

## Risks / Trade-offs

- **风险极低**：纯前端文案变更，不涉及逻辑或数据
- **回退方案**：恢复原来的 `<Button>` 即可
