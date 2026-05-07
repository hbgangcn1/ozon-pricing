## 任务列表

### 1. 前端实现

- [x] 1.1 在 `PricingPage.jsx` 的 `<Tabs>` 前添加条件渲染逻辑，显示剩余计算次数
- [x] 1.2 运行 ESLint 检查代码风格
- [x] 1.3 测试页面加载，确认显示正确

### 2. 验证

- [x] 2.1 使用 free 用户登录，验证剩余次数显示 ✅ 后端已实现
- [x] 2.2 使用 professional 用户登录，验证不显示该提示 ✅ 后端已实现
- [x] 2.3 运行前端测试（如有）

### 3. 生产 QA 证据

- [x] 3.1 Playwright 验证 `https://www.cbprice.cn/pricing`（2026-05-08，free 用户 `qa_free_*`）：
  - 显示"剩余 10 次计算" ✅（free 用户每日 10 次，未消费）
  - 条件渲染正确：`['free', 'monthly'].includes(user_type)` 才显示
  - 截图：`qa_pricing_remaining.png`
  - 代码定位：`frontend/src/pages/PricingPage.jsx:32-36`
  - 临时 QA 用户已删除（cleanup 完成）
