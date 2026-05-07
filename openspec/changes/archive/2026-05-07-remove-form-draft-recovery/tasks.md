## 1. 解除页面层接入（先解除依赖再删文件，避免构建瞬间断裂）

- [x] 1.1 修改 `frontend/src/pages/RegisterPage.jsx`：移除 `useDraftPersist` 和 `DraftRestoreDialog` 的 import；移除 `registerDraft` 实例化；移除 `draftData` / `draftDialogOpen` / 字段计数相关 state 与逻辑；移除 JSX 中 `<DraftRestoreDialog ... />` 渲染；保留并清理 `reset` 调用以确保正常注册流程不受影响
- [x] 1.2 修改 `frontend/src/pages/pricing/usePricingCalculation.js`：移除 `useDraftPersist` import；移除 `fastDraft` 与 `preciseDraft` 实例化；从 hook 返回值中移除这两项
- [x] 1.3 修改 `frontend/src/pages/PricingPage.jsx`：移除 `DraftRestoreDialog` import；移除从 `usePricingCalculation` 解构出的 `fastDraft` / `preciseDraft`；移除 `savedDrafts` / `draftDialogOpen` / 合并字段计数；移除 JSX 中 `<DraftRestoreDialog ... />` 渲染
- [x] 1.4 修改 `frontend/src/pages/logistics/useLogisticsPage.js`：移除 `useDraftPersist` import；移除 `draftState` 组合对象；移除 `logisticsDraft` 实例化；移除 `restoreDraft` 函数；从 hook 返回值中移除 `logisticsDraft` 与 `restoreDraft`
- [x] 1.5 修改 `frontend/src/pages/LogisticsPage.jsx`：移除 `DraftRestoreDialog` import；移除从 `useLogisticsPage` 解构出的 `logisticsDraft` / `restoreDraft`；移除 `draftDialogOpen` 与字段计数相关 state；移除 JSX 中 `<DraftRestoreDialog ... />` 渲染

## 2. 修正 LoginPage 过期提示文案

- [x] 2.1 修改 `frontend/src/pages/LoginPage.jsx`：将"您的会话已过期，登录后将恢复您的填写内容"改为"您的会话已过期，请重新登录"（toast 与内联警告框两处都改）；不改动触发条件（仍由 URL 参数 `?reason=expired` 触发）

## 3. 删除 hook 与组件本体

- [x] 3.1 删除文件 `frontend/src/hooks/useDraftPersist.js`
- [x] 3.2 删除文件 `frontend/src/components/DraftRestoreDialog.jsx`
- [x] 3.3 检查并删除 hook 的测试文件（`frontend/src/hooks/__tests__/useDraftPersist.test.js` 或同名 .jsx，如存在）
- [x] 3.4 删除文件 `frontend/src/__tests__/DraftRestoreDialog.test.jsx`

## 4. 清理测试用例

- [x] 4.1 修改 `frontend/src/__tests__/RegisterPage.test.jsx`：移除所有涉及 draft / DraftRestoreDialog / "包含 N 个字段" / sessionStorage 草稿相关的 `test` / `it` / `describe` 块；保留并确保非 draft 相关测试仍通过
- [x] 4.2 修改 `frontend/src/__tests__/PricingPage.test.jsx`：移除所有 draft 相关测试用例；保留并确保非 draft 相关测试仍通过
- [x] 4.3 修改 `frontend/src/__tests__/LogisticsPage.test.jsx`：移除所有 draft 相关测试用例；保留并确保非 draft 相关测试仍通过
- [x] 4.4 检查 `frontend/src/__tests__/LoginPage.test.jsx`（如存在）中是否有断言原过期提示文案的测试，同步更新断言文本

## 5. 全局清理与残留检查

- [x] 5.1 在 `frontend/src/` 下执行 `grep -ri "useDraftPersist"` 与 `grep -ri "DraftRestoreDialog"`，确认无任何残留引用
- [x] 5.2 在 `frontend/src/` 下执行 `grep -ri "draft:"` 与 `grep -ri "loadDraft\|clearDraft\|hasDraft"`，确认无任何残留引用
- [x] 5.3 在 `frontend/src/` 下执行 `grep -ri "检测到未完成"` 与 `grep -ri "登录后将恢复"`，确认无任何残留文案

## 6. Lint / 测试 / 构建验证

- [x] 6.1 在 `frontend/` 下运行 `npm run lint`（如脚本存在），修复所有 ESLint 错误（特别注意未使用的 import / 未使用的变量）
- [x] 6.2 在 `frontend/` 下运行 `npm run test`（Vitest 全量），所有测试必须通过，零警告零失败
- [x] 6.3 在 `frontend/` 下运行 `npm run build`，构建必须成功

## 7. 端到端验证（agent 自验，无需用户操作）

- [x] 7.1 通过 Playwright MCP（`/playwright` 技能）启动前端 dev 服务并打开 RegisterPage：在表单中输入字段后刷新页面，确认无"检测到未完成的填写"弹窗，确认 `sessionStorage` 中无新增 `draft:register` 键
- [x] 7.2 通过 Playwright MCP 打开 PricingPage：在 fast / precise 表单中输入字段后刷新，确认无弹窗，确认 `sessionStorage` 中无 `draft:pricing-fast` / `draft:pricing-precise` 键
- [x] 7.3 通过 Playwright MCP 打开 LogisticsPage：在表单中输入字段后刷新，确认无弹窗，确认 `sessionStorage` 中无 `draft:logistics-page` 键
- [x] 7.4 通过 Playwright MCP 触发会话过期（或直接访问 `/login?reason=expired`）：确认提示文案已更新为"您的会话已过期，请重新登录"
- [x] 7.5 关键验证步骤截图保存为证据

---

## QA 证据（生产 E2E 验证 - https://www.cbprice.cn）

- 7.1 `/register`：填表后刷新 → `draftKeys: []`、`hasDialog: false` → 截图 `7.1-register-no-draft.png`
- 7.2 `/pricing`（admin 已登录）：填表后刷新 → `draftKeys: []`、`hasDialog: false`、`allSession: []` → 截图 `7.2-pricing-no-draft.png`
- 7.3 `/logistics`：加载 → `draftKeys: []`、`hasDialog: false` → 截图 `7.3-logistics-no-draft.png`
- 7.4 `/login?reason=expired`：显示新文案"您的会话已过期，请重新登录"（`newText: true`），旧文案"登录后将恢复"已彻底移除（`oldText: false`）→ 截图 `7.4-login-expired.png`
- 6.1 `npm run lint` clean / 6.2 vitest 376/376 / 6.3 build success
