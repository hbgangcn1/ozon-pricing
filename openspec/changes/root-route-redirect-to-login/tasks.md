## 1. 路由表重组（App.jsx）

- [x] 1.1 在 `frontend/src/App.jsx` 顶部把 `Navigate` 加入 `react-router-dom` 的 import（若尚未引入）
- [x] 1.2 把现有 `<Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>` 拆成两段:
  - 独立 `<Route path="/" element={<Navigate to="/login" replace />} />`
  - 无 path 的父路由 `<Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>` 包裹原所有业务子路由
- [x] 1.3 删除原 `<Route index element={<PricingPage />} />`(根路径不再渲染 PricingPage)
- [x] 1.4 把所有业务子路由从 `path="pricing"` 等相对形式改为绝对路径 `path="/pricing"` 等(因父路由无 path,相对路径会失效)
- [x] 1.5 确认 14 个业务页 URL 全部保留: `/pricing`、`/logistics`、`/account`、`/users`、`/settings`、`/plans`、`/statistics`、`/subscription`、`/payment`、`/commission-categories`、`/logistics-pool`、`/product-import`、`/about`、`*`(NotFound)
- [x] 1.6 确认 AdminRoute 内部 fallback `Navigate to="/pricing"` 仍生效(无须改)
- [x] 1.7 本地手动验证: 已登录访问 `http://localhost:3001/` → 看到 LoginPage(已登录提示分支);访问 `/pricing` → 直达 PricingPage

## 2. ProtectedRoute returnTo 携带

- [x] 2.1 在 `App.jsx` 内 `ProtectedRoute` 组件中调 `useLocation()` 获取 `pathname` 与 `search`
- [x] 2.2 未登录跳转时构造 `loginUrl = `/login?returnTo=${encodeURIComponent(pathname + search)}``
- [x] 2.3 加保护: 若 `pathname === '/'` 则 loginUrl 直接为 `/login`(不带 returnTo);该分支为防御性,实际不会触发,因为 `/` 已被 task 1.2 的独立 Navigate 截胡
- [x] 2.4 替换原 `<Navigate to="/login" replace />` 为 `<Navigate to={loginUrl} replace />`

## 3. LoginPage 已登录态分支(LoginPage.jsx)

- [x] 3.1 从 `useAuthStore` 中读取 `isAuthenticated`、`user`、`logout`(确认 store 已暴露这些字段)
- [x] 3.2 在组件顶部计算 `const isLoggedIn = isAuthenticated && !!user`
- [x] 3.3 当 `isLoggedIn === true` 时渲染"已登录态"卡片,内容包含:
  - 文案 "您已登录为 {user.username}"
  - "继续使用" 按钮(primary)
  - "切换账户" 按钮(secondary)
- [x] 3.4 当 `isLoggedIn === false` 时渲染原登录表单(保持现有 UI 结构不变)
- [x] 3.5 **不得**使用 `useEffect(() => navigate(...), [isAuthenticated])` 自动跳转(违反规范)

## 4. 继续使用按钮(LoginPage.jsx)

- [x] 4.1 import `authAPI` from `services/api` 并准备 `useState` loading 标志
- [x] 4.2 实现 `handleContinue()`:
  ```
  setLoading(true)
  try {
    await authAPI.getMe()
    navigate(safeReturnTo(returnTo), { replace: true })
  } catch (err) {
    if (err.response?.status === 401) {
      logout({ skipServerCall: true }) // 或直接清 localStorage + Zustand state
      toast.error('登录已失效,请重新登录')
    } else {
      toast.error('网络错误,请重试')
    }
  } finally { setLoading(false) }
  ```
- [x] 4.3 确认 `authStore.logout` 支持 "本地清理不调后端" 模式;若不支持,新增辅助函数 `clearPersistedAuth()` 或在 logout 中识别 401 场景
- [x] 4.4 按钮 disabled 状态绑定 loading,防止重复点击

## 5. 切换账户按钮(LoginPage.jsx)

- [x] 5.1 实现 `handleSwitchAccount()`:
  ```
  await logout()  // 完整登出: 调 /auth/logout + 清本地
  // 不 navigate;组件因 isAuthenticated 变 false 自动重渲染为登录表单
  ```
- [x] 5.2 按钮在 logout 进行中显示 loading 态

## 6. 登录成功跳转目标(LoginPage.jsx)

- [x] 6.1 在文件顶部 import `useSearchParams`、添加 `safeReturnTo` 工具函数(可放 `frontend/src/lib/`)
- [x] 6.2 实现 `safeReturnTo(returnTo)` 严格按 design.md D4 规则:
  - 空 / 非 `/` 开头 / `//` 开头 → `/pricing`
  - `/` / `/login*` / `/register*` / `/forgot-password*` → `/pricing`
  - 其他 → 原值
- [x] 6.3 在登录成功 handler 中: `const returnTo = searchParams.get('returnTo'); navigate(safeReturnTo(returnTo), { replace: true })`
- [x] 6.4 确认现有 "登录后跳 /" 或 "跳 /pricing" 的硬编码全部替换

## 7. 测试更新与新增(Vitest + RTL)

- [x] 7.1 更新 `__tests__/LoginPage.test.jsx`:
  - 新增 case "未登录时渲染登录表单"(回归保护)
  - 新增 case "已登录时渲染提示卡片显示用户名 + 两个按钮,不渲染登录表单"
  - 新增 case "登录成功无 returnTo → navigate('/pricing')"
  - 新增 case "登录成功 returnTo=/logistics → navigate('/logistics')"
  - 新增 case "登录成功 returnTo=/ → navigate('/pricing')"(防循环)
  - 新增 case "登录成功 returnTo=/login → navigate('/pricing')"(防循环)
  - 新增 case "登录成功 returnTo=//evil.com → navigate('/pricing')"(防 open-redirect)
- [x] 7.2 新增 `__tests__/LoginPage.continue-session.test.jsx`:
  - case "已登录点击继续使用 + /auth/me 200 → navigate(returnTo||'/pricing')"
  - case "已登录点击继续使用 + /auth/me 401 → 清本地 + toast + 重渲染登录表单"
  - case "已登录点击继续使用 + 网络错误 → toast + 不清本地 + 按钮恢复"
- [x] 7.3 新增 `__tests__/LoginPage.switch-account.test.jsx`:
  - case "已登录点击切换账户 → 调 logout + 重渲染登录表单"
- [x] 7.4 更新或新增 `__tests__/App.routing.test.jsx`(若不存在则新建):
  - case "未登录访问 / → 重定向 /login (不带 returnTo)"
  - case "已登录访问 / → 重定向 /login (LoginPage 显示已登录提示)"
  - case "未登录访问 /pricing → 重定向 /login?returnTo=%2Fpricing"
  - case "未登录访问 /pricing?tab=detail → 重定向 /login?returnTo=%2Fpricing%3Ftab%3Ddetail"
  - case "已登录访问 /pricing → 直接渲染 PricingPage"
- [x] 7.5 检查并更新 `__tests__/LoginPage.session-restore.test.jsx`(可能与新逻辑冲突)
- [x] 7.6 跑 `npm run test --prefix frontend` 全量通过,无 warning

## 8. 手动验证(E2E 路径)

- [x] 8.1 启动后端 + 前端 dev server
- [x] 8.2 未登录场景: 访问 `http://localhost:3001/` → 看到登录表单 ✓
- [x] 8.3 未登录场景: 访问 `http://localhost:3001/logistics` → URL 变 `/login?returnTo=%2Flogistics`,登录成功后回跳 `/logistics` ✓
- [x] 8.4 已登录场景: 访问 `http://localhost:3001/` → 看到 "您已登录为 X" + 两按钮 ✓
- [x] 8.5 已登录场景: 点 "继续使用"(token 仍有效) → 跳 `/pricing` ✓
- [x] 8.6 已登录场景: 后端手动注销 session(或等 token 过期),再点 "继续使用" → 提示登录失效 + 显示登录表单 ✓
- [x] 8.7 已登录场景: 点 "切换账户" → 显示登录表单,可输入新账号 ✓
- [x] 8.8 直接访问业务页: 已登录访问 `http://localhost:3001/pricing` → 直接渲染 PricingPage(不经 /login)✓

## 9. 文档与收尾

- [x] 9.1 更新 `PLAN.md`(若 PLAN.md 仍跟踪此任务)记录路由行为变更
- [x] 9.2 在 PR 描述中明确标注 BREAKING(行为)以提醒 review
- [x] 9.3 部署后立即在生产域名 `cbprice.cn` 验证 task 8 全部场景
- [x] 9.4 跑 `openspec validate root-route-redirect-to-login --strict` 通过
