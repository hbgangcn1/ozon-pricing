## Why

精准定价模式下,管理员（及所有专业版及以上用户）刚登录跳转 `/pricing` 后,佣金类目下拉永远只显示"不使用类目 (0%)",已保存的"日化用品"等类目不出现。用户必须刷新页面才能看到。根因是 `usePricingCalculation` 的 `useEffect` 在首次渲染时同步读取 `useAuthStore.getState().hasProfessionalAccess()`,而此时 `LoginPage` 的 `setAuth` 与 `navigate('/pricing')` 在同一 tick 触发,React 订阅 commit 异步,`user` 在 store 中尚未填入,闸门返回 `false`,直接 `setCommissionCategories([])`,且依赖数组中没有 `user`,导致 `user` 后续就绪时 effect 永不重跑。证据已通过 React Fiber 反查确认 `PricingForm.props.commissionCategories.length === 0`,即便后端在同一会话内 200 返回了 501 字节的有效数据。

## What Changes

- 修复 `frontend/src/pages/pricing/usePricingCalculation.js` 中加载产品列表与佣金类目的 `useEffect`:加入 `user` 闸门(未就绪不发请求)并将关键的 `user` 字段（`id`、`subscription_type`、`role`）纳入依赖数组,使得 `user` 状态在登录后从 `null` 变为有值时 effect 自动重跑。
- 同时审查同文件其他依赖 `useAuthStore.getState()` 的副作用 hook(如物流规则加载),确保不存在相同的"首渲染时读 store 静态快照,后续 store 变化无法触发重跑"反模式。
- 新增 Playwright E2E 回归用例:`login → /pricing → 切到精准模式 → 打开佣金类目下拉`,断言下拉中能看到登录用户保存的所有类目以及"不使用类目 (0%)"占位项。
- 新增 Vitest 单元测试覆盖 `usePricingCalculation` 在 `user` 由 `null` 变为有值时是否正确触发数据加载。

## Capabilities

### New Capabilities
<!-- 无新 capability,本次修复属于已有 subscription-feature-gating 能力的行为修正 -->

### Modified Capabilities
- `subscription-feature-gating`: 新增"专业版门控的客户端资源在用户状态就绪后必须自动加载"这一行为契约。原 spec 描述了订阅升级按钮、试用按钮等 UI 门控,但未约束门控触发的"按订阅等级有条件加载的客户端数据"在登录直跳保护页时必须等到 `user` 真正在前端 store 中可读后再发起请求,本次为该 capability 增加该 SHALL 级别要求。

## Impact

- **代码**:`frontend/src/pages/pricing/usePricingCalculation.js`(修复)、`frontend/src/__tests__/usePricingCalculation.test.jsx`(新增或扩展)、`frontend/tests/e2e/pricing-commission-categories.spec.js`(新增 E2E)。
- **API**:无后端 API 变动;`GET /api/commission-categories`、`GET /api/products`、`GET /api/logistics` 行为不变。
- **依赖**:无。
- **运行时影响**:登录后首次请求佣金类目的时机从"页面 mount 同步触发(可能 user=null 而被跳过)"变为"`user` 写入 store 后触发(确保 `hasProfessionalAccess()` 正确判定)";对刷新页面进入 `/pricing` 的路径无可见影响,因为 `initAuth` 已在 React 首次渲染前同步从 `localStorage` 恢复 `user`。
- **风险**:若 `user` 永远不就绪(如 `initAuth` 失败),effect 不再发请求,下拉将保持只有"不使用类目 (0%)";但该场景下用户本就无法访问受保护页面,`AuthGuard` 会先一步重定向到 `/login`,故无新增暴露面。
