## Why

前端的 `useDraftPersist` + `DraftRestoreDialog` 机制在 Register、Pricing、Logistics 三个页面持续打扰用户：每次进入页面都可能弹出"检测到未完成的填写"模态框，且该弹窗阻塞页面交互（ESC 与点击外部均被禁用），用户只能在"恢复"和"丢弃"之间做选择。该机制存在多个固有缺陷——**提交成功后不清除草稿**导致已保存的数据被反复当作"未完成"询问、**字段计数把表单默认值也算进去**让"包含 32 个字段"成为虚张声势的恐吓数字、LogisticsPage 把筛选/分页/Tab 等 UI 状态也存为"草稿"——使其体验已与原始意图（帮用户省事）完全相反。决策：彻底移除该机制，前端不再做表单草稿持久化与恢复。

## What Changes

- **BREAKING**: 移除前端表单草稿自动持久化与恢复弹窗，所有页面不再保留任何未提交的表单内容
- 删除共享 hook `frontend/src/hooks/useDraftPersist.js` 及其单元测试
- 删除共享组件 `frontend/src/components/DraftRestoreDialog.jsx` 及其单元测试
- 从 `RegisterPage.jsx` 移除 `useDraftPersist` 接入、`draftDialogOpen` 状态、`DraftRestoreDialog` 渲染与字段计数逻辑
- 从 `PricingPage.jsx` 移除两份草稿（fast/precise）的接入、合并字段计数与对话框渲染
- 从 `LogisticsPage.jsx` 移除草稿弹窗渲染与 `restoreDraft` 调用
- 从 `pages/pricing/usePricingCalculation.js` 移除 `fastDraft` / `preciseDraft` 实例化与导出
- 从 `pages/logistics/useLogisticsPage.js` 移除 `draftState` 组装、`logisticsDraft` 实例化、`restoreDraft` 函数与导出
- 修改 `LoginPage.jsx` 中"您的会话已过期，登录后将恢复您的填写内容"提示文案，改为不承诺恢复填写内容的版本（草稿机制移除后该承诺已失效）
- 移除 Register/Pricing/Logistics 三个页面单元测试中所有 draft 相关用例
- 旧浏览器 sessionStorage 中残留的 `draft:*` 键不主动清理（sessionStorage 在标签页关闭时自然失效）

## Capabilities

### New Capabilities
- `form-state-handling`: 明确"前端不做表单草稿自动持久化与恢复"的产品决策与边界。该 capability 作为反向决策记录存在，防止未来重新引入同类机制时缺乏历史背景。

### Modified Capabilities

(无现有 capability 需要修改。)

## Impact

**受影响的前端代码（净删除约 600+ 行）**:
- `frontend/src/hooks/useDraftPersist.js`（删除）
- `frontend/src/hooks/__tests__/useDraftPersist.test.js`（如存在则删除）
- `frontend/src/components/DraftRestoreDialog.jsx`（删除）
- `frontend/src/__tests__/DraftRestoreDialog.test.jsx`（删除）
- `frontend/src/pages/RegisterPage.jsx`（移除草稿接入）
- `frontend/src/pages/PricingPage.jsx`（移除草稿接入）
- `frontend/src/pages/LogisticsPage.jsx`（移除草稿接入）
- `frontend/src/pages/LoginPage.jsx`（修改过期提示文案）
- `frontend/src/pages/pricing/usePricingCalculation.js`（移除 draft 实例化）
- `frontend/src/pages/logistics/useLogisticsPage.js`（移除 draft 状态与 restoreDraft）
- `frontend/src/__tests__/RegisterPage.test.jsx`（移除 draft 测试用例）
- `frontend/src/__tests__/PricingPage.test.jsx`（移除 draft 测试用例）
- `frontend/src/__tests__/LogisticsPage.test.jsx`（移除 draft 测试用例）

**用户可见行为变化**:
- 不再出现"检测到未完成的填写"弹窗
- 表单意外关闭/会话过期/导航离开页面后再次返回，已填写但未提交的内容**不会**被恢复——这是刻意的设计决定
- 登录页"会话已过期"的提示文案不再承诺恢复填写内容

**不受影响的范围**:
- `authStore` 中 `api_user` / `api_token` 的 localStorage 持久化（认证态恢复）保持原状
- CSRF cookie 机制保持原状
- SettingsPage 的数据库备份/恢复功能（与表单状态无关）保持原状
- 后端 API、数据库 schema、迁移脚本均无变化

**依赖与构建**:
- 不引入新依赖；不移除任何包级依赖（`useDraftPersist` 仅使用 React 内置 API 与 `sessionStorage`）

**风险**:
- 低。该机制并未在产品文档/营销中被宣传为功能；用户投诉表明现有体验是负价值；移除是减法操作，无回归路径上的隐式契约。
