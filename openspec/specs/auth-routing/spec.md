# auth-routing Specification

## Purpose
TBD - created by archiving change root-route-redirect-to-login. Update Purpose after archive.
## Requirements
### Requirement: 根路径必须永远指向登录页

系统 SHALL 在用户访问根路径 `/` 时,无论当前是否已登录,均立即重定向到 `/login`。

#### Scenario: 未登录用户访问根路径
- **WHEN** 未登录用户在浏览器地址栏输入 `https://www.cbprice.cn/` 或 `http://localhost:3001/`
- **THEN** 浏览器立即跳转到 `/login`,显示登录表单

#### Scenario: 已登录用户访问根路径
- **WHEN** 已登录用户(localStorage 存在 `api_user` 与 `api_token`)在浏览器地址栏输入根路径
- **THEN** 浏览器立即跳转到 `/login`,且 LoginPage 显示"已登录态"提示而非登录表单

#### Scenario: 根路径跳转不携带 returnTo 参数
- **WHEN** 任何用户访问根路径触发跳转
- **THEN** 跳转目标 URL 必须为 `/login`,不得包含 `?returnTo=/` 或 `?returnTo=` 任何形式的 query 参数

### Requirement: 业务页 URL 保持扁平且支持未登录回跳

系统 SHALL 保留所有业务页的现有扁平 URL(`/pricing`、`/logistics`、`/account`、`/users`、`/settings`、`/plans`、`/statistics`、`/subscription`、`/payment`、`/commission-categories`、`/logistics-pool`、`/product-import`、`/about`),且未登录用户访问业务页时携带 `returnTo` 参数跳转登录页。

#### Scenario: 已登录用户直接访问业务页
- **WHEN** 已登录用户访问 `https://www.cbprice.cn/pricing` 或其他业务页 URL
- **THEN** 系统直接渲染对应页面(PricingPage 等),不经登录页中转

#### Scenario: 未登录用户访问业务页
- **WHEN** 未登录用户访问 `https://www.cbprice.cn/logistics`
- **THEN** 浏览器跳转到 `/login?returnTo=%2Flogistics`,登录成功后回跳 `/logistics`

#### Scenario: returnTo 含 query 参数时正确编码
- **WHEN** 未登录用户访问 `https://www.cbprice.cn/pricing?tab=detail&id=123`
- **THEN** 跳转目标为 `/login?returnTo=%2Fpricing%3Ftab%3Ddetail%26id%3D123`(完整路径含 query 经 URL-encode)

### Requirement: 登录页在已登录态下显示提示而非自动跳转

`LoginPage` SHALL 在检测到用户已登录(`isAuthenticated === true && user 存在`)时,显示"您已登录为 {username}"提示卡片,提供"继续使用"与"切换账户"两个按钮,**不得调用 useEffect 自动 navigate**。

#### Scenario: 已登录用户进入登录页
- **WHEN** 已登录用户被重定向至 `/login`
- **THEN** 页面显示包含用户名的提示文本与两个按钮,登录表单不渲染

#### Scenario: 未登录用户进入登录页
- **WHEN** 未登录用户访问 `/login`
- **THEN** 页面显示登录表单,无"已登录"提示

### Requirement: 继续使用按钮必须验证后端会话有效性

`LoginPage` 的"继续使用"按钮 SHALL 在跳转业务页前调用后端 `/auth/me` 端点验证当前 token 仍被后端认可;验证失败必须清除本地持久化身份并停留在登录页显示登录表单。

#### Scenario: token 仍有效
- **WHEN** 已登录用户点击"继续使用"且后端返回 200
- **THEN** 浏览器跳转到 `returnTo` 指定的 URL(若有)或 `/pricing`(缺省)

#### Scenario: token 已失效
- **WHEN** 已登录用户点击"继续使用"且后端返回 401
- **THEN** 系统清除 localStorage 中的 `api_user` 与 `api_token`,清除 Zustand auth state,弹出 toast "登录已失效,请重新登录",同组件重新渲染为登录表单

#### Scenario: 验证请求网络错误
- **WHEN** 已登录用户点击"继续使用"且请求出现非 401 错误(网络错误、5xx)
- **THEN** 弹出 toast "网络错误,请重试",**不清除** localStorage,按钮恢复可点击状态

### Requirement: 切换账户按钮必须执行登出再显示登录表单

`LoginPage` 的"切换账户"按钮 SHALL 调用 `logout()` 完整登出流程(请求后端 `/auth/logout` + 清除本地持久化),完成后同组件渲染登录表单允许用户输入新凭据。

#### Scenario: 用户切换账户
- **WHEN** 已登录用户点击"切换账户"
- **THEN** 调用 `authStore.logout()`,清除 localStorage 与 Zustand state,组件重渲染显示登录表单

### Requirement: 登录成功跳转目标必须安全且非循环

登录表单提交成功后,系统 SHALL 跳转到 `returnTo` query 参数指定的 URL,缺省或非法值时跳 `/pricing`,**永远不得跳 `/`**。

#### Scenario: returnTo 为合法业务页
- **WHEN** 用户从 `/login?returnTo=%2Flogistics` 登录成功
- **THEN** 跳转到 `/logistics`

#### Scenario: returnTo 缺省
- **WHEN** 用户从 `/login`(无 returnTo)登录成功
- **THEN** 跳转到 `/pricing`

#### Scenario: returnTo 为根路径
- **WHEN** 登录页 URL 为 `/login?returnTo=%2F` 且登录成功
- **THEN** 跳转到 `/pricing`(防循环),不跳 `/`

#### Scenario: returnTo 为认证页路径
- **WHEN** returnTo 值为 `/login` / `/register` / `/forgot-password` 或以这些前缀开头
- **THEN** 跳转到 `/pricing`(防循环)

#### Scenario: returnTo 为外部 URL 或非法格式
- **WHEN** returnTo 值为 `https://evil.com/x` / `//evil.com` / `javascript:...` / 不以 `/` 开头
- **THEN** 跳转到 `/pricing`(防 open-redirect)

