## Context

当前 React Router v6 路由表把所有业务页挂在 `<Route path="/">` 下,通过 `<Route index>` 让 PricingPage 兼任"已登录首页"和"根路径默认渲染"双重职责。`ProtectedRoute` 把未登录踢回 `/login` 但不带 returnTo,登录成功跳转目标硬编码或不带参数。

`authStore.initAuth()` 启动时仅读 localStorage(`api_user` + `api_token`),不验证 token 有效性,导致"假登录态"长期存在。Oracle 已锁定 Q3=保持扁平 URL、Q4=`/login` 不自动跳走但显示"已登录"提示。

约束:
- 项目已上线,生产域名 cbprice.cn 有真实用户,业务页 URL 不能变
- React Router v6 + Zustand,无 SSR
- 后端 `/auth/me`(`api/routes/auth.py:479-495`)可用于验证 token 是否仍有效
- 测试栈 Vitest + React Testing Library

## Goals / Non-Goals

**Goals:**
- 根路径 `/` 永远落到 `/login`,无论登录态
- 业务页 URL 全部保持扁平不变(`/pricing`、`/logistics`、...),老书签直达
- `/login` 在已登录态下显式提示"您已登录为 X",由用户主动选择"继续"或"切换",不自动跳转
- "继续使用"按钮先调 `/auth/me` 验证后端是否仍认可,失败则清 localStorage 并显示登录表单(消除假登录态)
- ProtectedRoute 弹回登录时携带 `?returnTo=<原路径>`,登录后能回原页;但根路径 `/` 自身不带 returnTo
- 登录成功跳转目标:`returnTo` query param 优先,缺省 `/pricing`,**绝不跳 `/`**

**Non-Goals:**
- 不改 JWT 寿命 / Cookie SameSite / refresh 策略(Q3/Q4 评估时已剥离)
- 不引入 URL 命名空间前缀(`/app/*` / `/dashboard/*`)— Oracle 决策 Q3=选项 c
- 不改后端任何代码(只复用 `/auth/me`)
- 不实现"已登录提示页面"的登出按钮(切换账户=logout 后渲染登录表单,不需要新组件)
- 不改 `initAuth()` 本身(它仍只读 localStorage,验证职责前移到"继续使用"点击时;改 initAuth 风险面太大,留给后续 change)

## Decisions

### D1: 路由表重组方案 — Layout 路由去 path

**选**: 把 `<Route path="/" element={<ProtectedRoute><Layout/></ProtectedRoute>}>` 改成两段:
```jsx
<Route path="/" element={<Navigate to="/login" replace />} />
<Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
  <Route path="pricing" element={<PricingPage />} />
  ...
</Route>
```

**为什么不**:
- 不选 `/app/*` 前缀(Oracle Q3): 老书签全废,无收益
- 不选保留 `<Route path="/">` + 把 index 改 redirect: index 路由仍会被 ProtectedRoute 包裹,未登录态下根路径会先经 ProtectedRoute → /login,与"无论登录态"语义不符;而且让 `/` 仍受 Protected 包裹增加心智负担

**关键点**:
- 必须移除原 `<Route index element={<PricingPage />} />`(因为父路由不再有 path="/")
- Layout 路由用 "无 path" 形式,React Router v6 支持(parent route without path)
- `<Route path="*" element={<NotFoundPage />}>` 在 Layout 子路由内的 catch-all 与外层 catch-all 共存——保持原有结构

### D2: ProtectedRoute returnTo 携带规则

**选**: ProtectedRoute 用 `useLocation()` 拿当前 pathname,构造 `<Navigate to={`/login?returnTo=${encodeURIComponent(pathname + search)}` replace />`。

**关键约束**:
- 若 `pathname === '/'` → 不带 returnTo(直接 `Navigate to="/login" replace`)— 但实际上 `/` 已被 D1 的独立 Navigate 截胡,根本走不到 ProtectedRoute,所以这条是防御性
- 只对真实业务页带 returnTo,因为登录后跳 `/` 等于绕回登录页死循环
- `returnTo` 必须 URL-encode,因为 query 中可能有 `?` `&`

**为什么不**:
- 不用 location.state 传 returnTo: 刷新就丢,不可靠
- 不用 sessionStorage 暂存: 多 tab 干扰

### D3: LoginPage 已登录态分支 — 显式按钮 vs 自动跳

**选**: 渲染时检测 `isAuthenticated && user`,显示提示卡片 + 两个按钮(继续 / 切换),**不用 useEffect 自动 navigate**。

**为什么不自动跳**:
- 与 Q1 "/ 永远是登录页" 冲突: 用户从 / 被 D1 弹到 /login,又被 useEffect 跳走,等于绕回首页,Q1 失效
- 自动跳还会触发 ProtectedRoute → 假登录态触发 401 → 拦截器再跳 /login → 死循环

**"继续使用"按钮的实现**:
```js
async function handleContinue() {
  setLoading(true)
  try {
    await authAPI.getMe()  // 调 /auth/me 验证
    navigate(returnTo || '/pricing', { replace: true })
  } catch (err) {
    if (err.response?.status === 401) {
      clearPersistedAuth()  // 清 localStorage + Zustand state
      // 不 navigate,本组件就会因 isAuthenticated 变 false 重新渲染登录表单
      toast.error('登录已失效,请重新登录')
    } else {
      toast.error('网络错误,请重试')
    }
  } finally {
    setLoading(false)
  }
}
```

**"切换账户"按钮的实现**:
```js
async function handleSwitchAccount() {
  await logout()  // 调 /auth/logout + 清 localStorage
  // 组件重渲染,显示登录表单
}
```

### D4: 登录成功跳转目标

**选**: `navigate(returnTo || '/pricing', { replace: true })`,其中 `returnTo` 来自 `useSearchParams().get('returnTo')`。

**关键校验**:
- 若 `returnTo === '/'` 或 `returnTo === '/login'` 或 `returnTo` 以 `/login` / `/register` / `/forgot-password` 开头 → 视为非法,缺省 `/pricing`
- 否则只允许相对路径(以 `/` 开头但不以 `//` 开头),防 open-redirect

```js
function safeReturnTo(returnTo) {
  if (!returnTo) return '/pricing'
  if (!returnTo.startsWith('/')) return '/pricing'
  if (returnTo.startsWith('//')) return '/pricing'
  if (returnTo === '/' || returnTo.startsWith('/login') ||
      returnTo.startsWith('/register') || returnTo.startsWith('/forgot-password')) {
    return '/pricing'
  }
  return returnTo
}
```

### D5: 假登录态处理边界

**选**: 不改 `initAuth()`,把验证延后到"继续使用"点击时。

**为什么**:
- 改 `initAuth()` 让它启动时调 `/auth/me`,会让所有未登录访问公开页(`/login`、`/register`)都多一次后端请求,且 loading 期间 UI 闪烁(原 30ms → 200ms+)
- 假登录态在新方案下唯一的入口是"已登录用户访问 /"(被弹到 /login),用户必须主动点"继续"才会触发后端调用,自然且无浪费

**遗留**: 已登录用户访问业务页 URL(如直接打开 cbprice.cn/pricing)时,假登录态仍会让 ProtectedRoute 放行,后续 API 调用 401 才被踢出。这个由现有的 axios interceptor + sessionKicked 机制兜底,**不在本 change 范围内**。

## Risks / Trade-offs

- [LoginPage 已登录态显示"您已登录为 X" 增加 UX 摩擦] → 已与用户确认是期望行为(Q1 + Q4),可接受
- [returnTo 校验若覆盖不全可能引入 open-redirect] → D4 显式白名单(只接受 `/` 开头且非 `//` 开头且非认证页)
- [Layout 路由从 `<Route path="/">` 改成无 path 可能影响 useMatch / useResolvedPath 等钩子] → 项目内 grep 确认无依赖,且 Layout 子路由用 outlet 渲染不受影响
- [测试用例需大量更新,可能掩盖回归] → tasks.md 强制每个测试改动单独 commit,review 时易追溯
- [生产部署后,已登录用户首次访问根域名会看到"已登录提示"页面,可能误以为故障] → 提示文案明确说明状态,提供清晰按钮;部署前可在 about 页加变更说明

## Migration Plan

**部署步骤**:
1. 改 App.jsx 路由表(D1 + D2)
2. 改 LoginPage.jsx(D3 + D4)
3. 更新现有测试 + 新增测试
4. 本地 manual QA: 已登录访问 / / 业务页直达 / 假登录态 / returnTo 链路 / 切换账户
5. 合并到 main → 自动部署生产
6. 部署后立即验证 cbprice.cn/ → /login,cbprice.cn/pricing → 直达(已登录),cbprice.cn/pricing → /login?returnTo=/pricing(未登录)

**回滚策略**:
- 单 commit 改造,git revert 即可
- 无数据库 schema 变更,无需 migration 回退
- localStorage 数据不变,回滚后用户体验立即恢复

## Open Questions

无。所有关键问题已通过 Q1/Q2(用户)+ Q3/Q4(Oracle)锁定。
