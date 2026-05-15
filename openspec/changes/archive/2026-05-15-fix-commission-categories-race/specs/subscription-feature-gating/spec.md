## ADDED Requirements

### Requirement: 专业版门控的客户端资源在用户状态就绪后自动加载
任何在前端按订阅等级有条件加载的客户端资源(典型示例:精准定价模式下的佣金类目列表)SHALL 在登录直跳受保护页面的路径下,等待 `useAuthStore.user` 真正写入 store 后再发起加载请求,且当 `user` 由 `null` 变为有值或其 `subscription_type`/`role` 变化时,加载逻辑 SHALL 自动重跑。系统不允许出现"首次渲染时 user 未就绪 → 跳过加载 → 后续 user 就绪但加载逻辑不再触发"的死锁状态。

#### Scenario: 登录直跳后佣金类目下拉立即可见
- **WHEN** 专业版/企业版/管理员用户在 `/login` 输入正确凭据,前端调用 `setAuth(user, token)` 后通过 `navigate('/pricing')` 跳转,且用户进入精准定价模式打开"佣金类目"下拉
- **THEN** 下拉中 SHALL 包含该用户已保存的所有佣金类目以及"不使用类目 (0%)"占位项,无需手动刷新页面

#### Scenario: 用户状态从未就绪变为就绪时数据加载逻辑重跑
- **WHEN** `usePricingCalculation` hook 的副作用在首次渲染时观察到 `user` 为 `null`,随后 Zustand store 中 `user` 被填入有效对象
- **THEN** 该副作用 SHALL 自动重跑,并按 `useAuthStore.getState().hasProfessionalAccess()` 的最新返回值决定是否调用 `commissionCategoriesAPI.getAll()`,且将返回数据写入组件 state

#### Scenario: 未登录或 user 未就绪不发起受保护资源请求
- **WHEN** `usePricingCalculation` hook mount 时 `user` 为 `null`(例如刚开始解析 token、initAuth 失败)
- **THEN** hook SHALL 跳过 `productsAPI.getAll()` 与 `commissionCategoriesAPI.getAll()` 的调用,不发出任何带 Authorization header 的请求,以避免无效 401 噪音

#### Scenario: 用户订阅升级后受门控资源自动可见
- **WHEN** 已登录的免费版用户在 `/pricing` 页面成功完成升级支付,前端通过 `setUser` 将 `subscription_type` 由 `free` 更新为 `professional`
- **THEN** `usePricingCalculation` hook 的数据加载副作用 SHALL 因 `user.subscription_type` 变化而重跑,并自动调用 `commissionCategoriesAPI.getAll()`,佣金类目下拉在不刷新页面的情况下从空白变为含完整类目列表

#### Scenario: 刷新进入受保护页面无回归
- **WHEN** 已登录用户直接刷新 `/pricing` 页面,`App.initAuth()` 在 React 首次渲染前从 sessionStorage/localStorage 同步恢复 `user` 与 `token`
- **THEN** `usePricingCalculation` hook 在首次渲染时即观察到 `user` 已就绪,SHALL 立即调用 `commissionCategoriesAPI.getAll()`,佣金类目下拉首屏可见
