## 1. 前端实现

- [x] 1.1 在 `SubscriptionPage.jsx` 的 `loadInitial` 和 `fetchSubscription` 中确保 `expired_at` 被保存到 `currentPlan` state
- [x] 1.2 在"当前套餐"卡片中增加到期时间展示行，格式 `yyyy-mm-dd hh:mm:ss`
- [x] 1.3 确保免费版和管理员角色不显示到期时间（保持"永久有效"Badge）

## 2. 测试补充

- [x] 2.1 更新 `SubscriptionPage.test.jsx`，增加"付费订阅展示到期时间"场景
- [x] 2.2 增加"免费版不展示到期时间"场景

## 3. 验证

- [x] 3.1 运行前端单元测试 `npm run test`，确保现有测试全部通过
- [x] 3.2 运行 flake8，确保无 Python 代码变更引发的 lint 错误（后端零改动，此步骤应自动通过）
