## Context

`/pricing` 是受 `AuthGuard` 保护的页面,正常使用流程有两种:
1. **登录跳转路径**:用户在 `/login` 提交表单 → `LoginPage.onSubmit` 调用 `useAuthStore.setAuth(user, access_token)` 写入 store + sessionStorage,然后立即 `navigate('/pricing')`(同一 React tick 内)。
2. **刷新/直接访问路径**:用户已持有有效 session,刷新页面 → `App.useEffect` 调用 `initAuth()` 同步从 sessionStorage/localStorage 恢复 token + user,在 React 首次渲染前 store 已就绪。

`PricingPage` mount 时调用 `usePricingCalculation(user)` hook,该 hook 内有一个 `useEffect`(目前位于 `usePricingCalculation.js:65-89`)负责并行加载 `productsAPI.getAll()` 和、当用户具备专业版及以上权限时的、`commissionCategoriesAPI.getAll()`:

```js
useEffect(() => {
  let cancelled = false
  const loadData = async () => {
    const canFetchCommission = useAuthStore.getState().hasProfessionalAccess()
    const [productData, commissionData] = await Promise.all([
      productsAPI.getAll(),
      canFetchCommission ? commissionCategoriesAPI.getAll() : Promise.resolve([]),
    ])
    if (!cancelled) {
      setProducts(Array.isArray(productData) ? productData : [])
      setCommissionCategories(Array.isArray(commissionData) ? commissionData : [])
    }
  }
  loadData()
  return () => { cancelled = true }
}, [refreshCommissionCategories, refreshProducts])
```

`hasProfessionalAccess()` 内部依赖 `user`:

```js
hasProfessionalAccess: () => {
  if (get().isAdmin()) return true
  return PROFESSIONAL_TIERS.includes(get().getSubscriptionType())
}
```

而 `isAdmin()` 又依赖 `user.role === 'admin'`,`getSubscriptionType()` 依赖 `user.subscription_type`。

**问题观察(2026-05 admin 实测)**:
- `curl -H "Authorization: Bearer <admin-token>" /api/commission-categories` → `200` + `[{id:3562,name:"日化用品",...}]`(后端 OK)。
- 浏览器 console 手动 `fetch('/api/commission-categories', {headers:{Authorization:`Bearer ${ssToken}`}})` → 同样 `200` + 完整数据。
- `performance.getEntriesByName('http://localhost:3001/api/commission-categories','resource')` 显示 3 次请求,全部 `status:200, size:501`。
- 通过 React Fiber 反查 `PricingForm.props.commissionCategories` → `length:0, sample:[]`。

→ 数据在网络层全部就位,但组件树里 `commissionCategories` 始终为空数组,下拉因此只渲染占位项 `不使用类目 (0%)`。

**根因**:登录直跳路径下,`PricingPage` 首次 render 时 `LoginPage` 刚同步调用了 `setAuth`,Zustand store 内部的 `user` 字段同步写入,但订阅 `useAuthStore((s) => s.user)` 的 `PricingPage` 在那次 render 中拿到的依然是上一帧的 `null`(React 18 的 store 订阅 commit 异步)。`usePricingCalculation` 的 `useEffect` 在该次 render 后触发 `loadData`,内部 `useAuthStore.getState()` 读到的也是过渡瞬间的 store —— 在某些时序下 `user` 已写入返回 admin,但在 `PricingForm` 已 mount 用 `null` 渲染之后,`useEffect` 跑在写入完成前的窗口同样存在。这一非确定性时序解释了"3 次请求都成功但 state 仍是 `[]`"的现象的真正含义:那 3 次请求来自后续重渲染或其他路径(例如汇率查询的副作用、StrictMode 双调用),但 `usePricingCalculation` 自己的那一次 effect 在 user=null 窗口跑完了 `Promise.resolve([])` 分支并写入 `setCommissionCategories([])`,而后续 `user` 真正就绪也无法再触发该 effect —— 因为依赖数组是 `[refreshCommissionCategories, refreshProducts]`,二者均为 `useCallback(..., [])` 稳定引用。

## Goals / Non-Goals

**Goals:**
- 登录直跳 `/pricing` 后,佣金类目下拉立即包含用户已保存的所有类目(以及"不使用类目 (0%)"占位项),无需手动刷新。
- 修复方案对刷新进入 `/pricing` 的路径无回归(原本就工作的不被破坏)。
- 同一 hook 内其他依赖 `useAuthStore.getState()` 的副作用(如 `checkLogistics`)也应审计,确保不存在同类竞态。
- 提供 Vitest 单元测试与 Playwright E2E 双重回归保护。

**Non-Goals:**
- 不修改后端 `/api/commission-categories` 的鉴权或返回结构(已验证后端正确)。
- 不引入新的状态管理库(继续使用 Zustand)。
- 不重构整个 `usePricingCalculation` hook(>200 行),仅修改两个相关的 `useEffect`。
- 不调整 `LoginPage` 的 `setAuth` + `navigate` 顺序(改 LoginPage 影响面更大)。
- 不修改 `useAuthStore` 的 `setAuth`/`hasProfessionalAccess`(它们语义正确,问题在调用时机)。

## Decisions

### Decision 1: 在 `useEffect` 闸门 + 依赖数组中加入 `user`,而非订阅 `hasProfessionalAccess` 的派生值

**选择**:
```js
const user = useAuthStore((state) => state.user)

useEffect(() => {
  if (!user) return  // user 未就绪不发请求
  let cancelled = false
  const loadData = async () => {
    const canFetchCommission = useAuthStore.getState().hasProfessionalAccess()
    // ... 原逻辑
  }
  loadData()
  return () => { cancelled = true }
}, [refreshCommissionCategories, refreshProducts, user?.id, user?.subscription_type, user?.role])
```

**为什么**:
- 直接订阅 `user` 是 Zustand 的 idiomatic 做法,且 hook 内已经接收 `user` 作为参数(从 `PricingPage` 透传),无需额外订阅 —— 直接用现有 `user` 参数即可。
- `user?.id`/`user?.subscription_type`/`user?.role` 三个原始值放入依赖数组,可保证:
  - 登录前 user=null → effect 不发请求(避免无意义的 401 噪音)
  - 登录后 user 写入 → effect 重跑,此时 store 状态稳定,`hasProfessionalAccess()` 返回正确值
  - 用户改变订阅(如试用激活)→ effect 重跑,自动加载之前被门控的数据
- 不订阅 `hasProfessionalAccess()` 派生值,因为它是函数(每次 render 返回新引用),会导致 effect 无限循环。

**被否决的备选方案**:
- **A. 监听 `useAuthStore.subscribe`**:复杂度更高,需要手动管理 unsubscribe,且偏离 hook 的声明式风格。
- **B. 在 `LoginPage` 中 `await` user 写入完成再 navigate**:Zustand 的 `setState` 是同步的,无法 await;需要引入 setTimeout/microtask hack,污染 LoginPage。
- **C. 把首次加载延迟到 `PricingForm` 内部 effect**:责任错位,数据加载应在 hook 层而非展示组件。

### Decision 2: `user` 加入依赖时只取原始值字段,不取整个对象引用

**选择**:`[refreshCommissionCategories, refreshProducts, user?.id, user?.subscription_type, user?.role]`

**为什么**:
- 整个 `user` 对象在某些路径(如 `setUser` 重新赋值同等内容)下会产生新引用,导致 effect 多余重跑。
- 仅监听 3 个真正影响 `hasProfessionalAccess()` 输出的字段,既避免过度触发,又确保关键变化被捕获。
- 用 optional chaining `user?.id` 处理 user=null 的初始状态,避免运行时错误。

### Decision 3: 同样模式应用到同文件内的 `checkLogistics` effect(line 97-118)

**选择**:`checkLogistics` 当前依赖数组为 `[]`(只在 mount 跑一次),但其调用 `logisticsAPI.getAll()` 同样需要带 token 鉴权。审计后若其在 user=null 时被静默吞 401(catch 块设置 `setHasLogisticsRules(true)`),用户可能看到错误的"已有物流规则"假阳性。

**修复方案**:同样加入 `if (!user) return` 闸门 + `user?.id` 依赖。

**为什么**:
- 一次性修干净所有同类反模式,避免后续踩同样的坑。
- `checkLogistics` 在 `[]` 依赖下首次也是 user=null 窗口运行,只是症状被 catch 块掩盖。

### Decision 4: 测试策略 = Vitest 单元 + Playwright E2E 双覆盖

**Vitest 单元** (`frontend/src/__tests__/usePricingCalculation.test.jsx`):
- mock `useAuthStore` 与 `commissionCategoriesAPI`/`productsAPI`
- 场景 1:hook mount 时 user=null → 断言 `commissionCategoriesAPI.getAll` **未被调用**
- 场景 2:hook mount 时 user=null,然后 user 被设置为 admin → 断言 `commissionCategoriesAPI.getAll` 被调用 1 次,且 `commissionCategories` state 含返回数据
- 场景 3:hook mount 时 user 已是 admin → 断言立即调用 + 数据写入
- 场景 4:hook mount 时 user 是 free → 断言不调用 commissionCategoriesAPI(走 `Promise.resolve([])`)

**Playwright E2E** (`frontend/tests/e2e/pricing-commission-categories.spec.js`):
- 前置:确保 admin 用户有至少 1 个佣金类目(若没有,通过 API 创建)
- 步骤:打开 `/login` → 输入凭据 → 等待 `/pricing` URL → 切到精准模式 → 点开"佣金类目"下拉
- 断言:下拉里包含"日化用品"(或 fixture 类目名)+ "不使用类目 (0%)"
- 反向断言:刷新页面后下拉内容不变(确保无回归)

## Risks / Trade-offs

- **[Risk] 添加依赖后 effect 重跑次数增加** → Mitigation:`user?.id` 等是稳定原始值,只有真正登录/登出/改订阅时才变化;实测 mount + 登录变化 = 2 次最多,可接受。
- **[Risk] `checkLogistics` 加闸门后,本地开发若 store 初始化失败可能误判"无物流规则"** → Mitigation:catch 块仍保留 `setHasLogisticsRules(true)` 兜底语义;闸门只是延迟首次请求,不改变最终行为。
- **[Risk] Playwright E2E 测试需要稳定的 admin fixture,可能与 CI 环境冲突** → Mitigation:E2E 用例自身负责创建/清理类目,不依赖外部数据库 seed。
- **[Trade-off] 不修复登录路径的根本时序问题(`setAuth` 与 `navigate` 同 tick)** → 选择在数据加载层修复而非身份层修复,因为身份层修改影响面大、回归风险高;数据加载层加 user 闸门是局部、可测的最小改动。
- **[Risk] 若未来有新页面、新 hook 同样在 user 未就绪时读 `useAuthStore.getState()` 做条件判断** → Mitigation:在 `frontend/AGENTS.md`(若存在)或本 change 的 design.md 中记录该反模式,作为代码 review 检查点。

## Migration Plan

无数据库或 API 兼容性问题,纯前端修复:

1. 改 `usePricingCalculation.js`(2 个 effect)。
2. 跑 Vitest:`cd frontend && npm run test -- usePricingCalculation`。
3. 跑 Playwright E2E:`cd frontend && npm run test:e2e -- pricing-commission-categories`。
4. 本地手工验证:重启前端 dev server,清 sessionStorage/localStorage,登录 admin → 直接看 `/pricing` 精准模式佣金类目下拉。
5. 部署:遵循 `AGENTS.md` 标准 deploy 流程(`git push origin main` → SSH `git pull` → `nohup bash deploy/deploy.sh`)。
6. 部署后回归:在 `https://www.cbprice.cn` 重新验证一次。

**Rollback**:`git revert` 单 commit + 重新 deploy;无 schema 变化无需回滚迁移。
