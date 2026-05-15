## Why

效率版和专业版用户订阅成功后，在订阅管理页面无法看到订阅到期时间，导致用户不清楚自己的订阅何时过期。需要在前端"当前套餐"卡片中增加到期时间展示。

## What Changes

- 前端 `SubscriptionPage` 中保存并展示后端已返回的 `expired_at` 字段
- 在"当前套餐"卡片中增加一行"到期时间：yyyy-mm-dd hh:mm:ss"文字
- 免费版和管理员角色保持现有"永久有效"展示，不显示到期时间
- 补充前端单元测试，验证到期时间的格式化展示逻辑

## Capabilities

### New Capabilities

（无新能力引入，纯前端展示增强）

### Modified Capabilities

（无spec级别需求变更）

## Impact

- **前端**: `frontend/src/pages/SubscriptionPage.jsx`
- **测试**: `frontend/src/__tests__/SubscriptionPage.test.jsx`
- **后端**: 零改动，`/api/subscriptions/current` 接口已返回 `expired_at`
