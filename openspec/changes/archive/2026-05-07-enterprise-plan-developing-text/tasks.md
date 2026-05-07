## 1. 前端修改

- [x] 1.1 在 `SubscriptionPage.jsx` 中将企业版的 `<Button>联系客服升级</Button>` 替换为居中显示的"开发中……"文字（`<span>` 或 `<div>`），保持与其他卡片底部对齐
- [x] 1.2 移除不再需要的 `plan.developing` 相关逻辑（如有）

## 2. 测试更新

- [x] 2.1 检查前端测试中是否有断言"联系客服升级"按钮的用例，如有则更新为断言"开发中……"文字
- [x] 2.2 运行前端测试确认全部通过

## 3. 部署

- [x] 3.1 本地构建前端并部署到生产服务器

## 4. 生产 QA 证据

- [x] 4.1 Playwright 验证 `https://www.cbprice.cn/subscription`（2026-05-08）：
  - 企业版卡片底部"开发中……"文字出现 1 次 ✅
  - "开发中" Badge 出现 ✅
  - 旧文案"联系客服"已不存在 ✅
  - 截图：`qa_subscription_developing.png`
  - 代码定位：`frontend/src/pages/SubscriptionPage.jsx:298-301`
