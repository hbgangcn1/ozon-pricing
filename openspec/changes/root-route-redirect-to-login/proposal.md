## Why

当前根路径 `/`(`http://localhost:3001/` / `https://www.cbprice.cn/`)的行为是:已登录用户直接进入业务首页(PricingPage),未登录才跳 `/login`。但产品期望"根路径永远是登录页"——即便已登录用户访问根域名也应被引导到登录页面,以满足品牌入口和身份切换的需要。

更深层的问题是 `initAuth()` 仅从 localStorage 恢复身份,**从不在启动时验证 token 是否仍有效**,导致 token 已废、session 被踢、其他设备登出等场景下,本机依然显示"已登录"假象,直接放进首页。

## What Changes

- **BREAKING(行为)**: 根路径 `/` 不再渲染 PricingPage,改为永远 `<Navigate to="/login" replace />`
- 业务页 URL 全部保持扁平不变(`/pricing`、`/logistics`、`/account`、`/users` 等 14 个),老书签直达对应页面
- `ProtectedRoute` 在踢回登录页时携带 `?returnTo=<原路径>`,登录成功后回跳;但根路径 `/` 自身不带 `returnTo`(避免登录后又回 `/` 再循环弹回登录页)
- `LoginPage` 新增"已登录态"分支:检测到 `isAuthenticated && user` 时显示 "您已登录为 {username}" 提示,提供两个按钮 — "继续使用"(先调 `/auth/me` 验证,成功跳 `/pricing`,失败清 localStorage 留在登录表单)和 "切换账户"(`logout()` 后显示登录表单)
- 登录成功跳转目标:优先 `returnTo` query param,缺省 `/pricing`(绝不能跳 `/`,否则死循环)
- 前端测试同步更新:涵盖根路径行为、已登录态登录页提示、returnTo 不污染 `/`

## Capabilities

### New Capabilities
- `auth-routing`: 前端路由的认证状态映射规则 — 根路径行为、ProtectedRoute returnTo 机制、LoginPage 已登录态分支、登录成功跳转目标

### Modified Capabilities
<!-- 无;auth-routing 是首次正式建模 -->

## Impact

- **前端代码**:
  - `frontend/src/App.jsx` — 路由表重组(根路径独立 + Layout 路由去 path)
  - `frontend/src/pages/LoginPage.jsx` — 新增已登录态分支 UI + 登录成功跳转改造
  - `frontend/src/components/ProtectedRoute`(在 App.jsx 内)— 携带 returnTo 参数
- **前端测试**:
  - 现有 `LoginPage.test.jsx`、`LoginPage.session-restore.test.jsx`、`App.routing*.test.jsx`(若存在)需更新
  - 新增测试:根路径已登录用户被弹回 `/login`、`/login` 已登录态显示提示、returnTo 不带 `/` 值
- **后端**: 无改动(仅依赖现有 `/auth/me` 端点做"继续使用"前的验证)
- **生产 URL 兼容性**: 所有业务页 URL 保持不变,老书签零影响
- **用户体验**:
  - 已登录用户访问根域名会多看到一次"您已登录为 X"提示页面(原行为是直接进首页)
  - 假登录态(localStorage 有数据但 token 已废)将通过"继续使用"按钮的验证步骤被显式清理,不再静默放行
