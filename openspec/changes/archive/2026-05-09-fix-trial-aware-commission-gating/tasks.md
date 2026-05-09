# Implementation Tasks

依赖图：T1 (后端 schema/dep/auth response) → T2 (后端 GET 闸门) → T3/T4 (后端测试) → T5 (前端 authStore) → T6 (CommissionCategoriesPage) → T7 (usePricingCalculation) → T8 (前端测试) → T9 (Manual QA) → T10 (lint+全套测试+commit+archive)
T1 与 T2 可并行（不同文件）；T6 与 T7 可并行（不同文件）。

## 1. 准备 / 审计（必须先做）

- [x] 1.1 读 `requirements.txt` 确认 Pydantic v2（已在 README 锁定，复核即可）
- [x] 1.2 `rg "hasProfessionalAccess|hasEnterpriseAccess|user_type === 'free'|subscription_type ==" frontend/src` 确认本次改动的 blast radius 仅 `CommissionCategoriesPage` + `usePricingCalculation`；若发现其他页面引用 `hasProfessionalAccess`（如 SubscriptionPage 已知会用），评估是否需扩展守卫
- [x] 1.3 读 `db/users.py` 的 `get_user_by_id` / `verify_user`，确认 SELECT 返回包含 4 个 `trial_*` 字段；如缺失则补上
- [x] 1.4 读 `services/plan_resolution.py:29-46` 复核 `is_in_trial` / `get_effective_plan` 当前签名（避免后续 import 错位）；**0 修改**
- [x] 1.5 读 `api/routes/commission_categories.py:21-34, 65-70` 找到 GET 路由当前 dep + helper 当前实现（已用 SimpleNamespace 包装，仅需 rename + 接入 GET）
- [x] 1.6 读 `frontend/src/pages/CommissionCategoriesPage.jsx:16-27, 44-79` 确认页面内**本地** `UpgradePrompt` 函数（行 16-27 定义，**非**共享组件、**无** import）+ 两处 fetch 入口位置
- [x] 1.7 读 `frontend/src/pages/pricing/usePricingCalculation.js:39, 61-84` 确认 `refreshCommissionCategories` 与初始 useEffect 两处 commission API 调用位置

## 2. 后端：schema + dep + auth response（Wave 1，T1）

- [x] 2.1 在 `api/models/schemas.py::UserResponse` 追加 4 个**非 Optional**字段（与 ORM NOT NULL server defaults 对齐）：
  ```python
  trial_used: int = 0
  trial_started_at: int = 0
  trial_expires_at: int = 0
  trial_plan_at_start: str = ""
  ```
  顺序与 ORM 一致：`trial_used → trial_started_at → trial_expires_at → trial_plan_at_start`
- [x] 2.2 在 `api/dependencies.py::get_current_user`（line 139-154）返回 dict 末尾追加同 4 字段，值用 `user.trial_used or 0` / `user.trial_plan_at_start or ""` 等回落表达
- [x] 2.3 在 `api/dependencies.py::get_user_with_subscription`（line 157-171）返回 dict 末尾追加同 4 字段（commission_categories 路由依赖此 dep）
- [x] 2.4 在 `api/routes/auth.py` 三处 `UserResponse(...)` 构造点同步透传 4 字段：
  - login response（line 200-209）：source 是 dict + ORM 混合，按各处实际 source 取值
  - register response（line 341-350）：source 是 ORM `user_data`
  - `/me` response（line 483-495）：source 是 user dict
  缺值时回落 0 / `""`
- [x] 2.5 `python -m flake8 api/models/schemas.py api/dependencies.py api/routes/auth.py` 通过

## 3. 后端：commission GET 闸门 + helper rename（Wave 1，T2，与 T1 并行）

- [x] 3.1 `api/routes/commission_categories.py` rename helper：`_ensure_commission_write_access` → `_ensure_commission_access`（语义不再仅限写）；helper 内部 `get_effective_plan(SimpleNamespace(**user))` 调用逻辑保持不变；**但 HTTPException detail 必须从 "此功能需要专业版或更高订阅等级" 改为中性文案 "当前方案暂不支持此功能"**（移除 "专业版" 标签以满足 spec.md:5 / spec.md:13 不暴露 plan 标签的要求）
- [x] 3.2 把 POST/PATCH/DELETE 三处 `_ensure_commission_write_access(user)` 调用全部改为 `_ensure_commission_access(user)`
- [x] 3.3 GET 端点 `list_categories`：把 `Depends(get_current_user_id)` 改为 `Depends(get_user_with_subscription)`，开头调用 `user_id = _ensure_commission_access(user)`
- [x] 3.4 删除文件顶部 `from api.dependencies import get_current_user_id`（不再使用）
- [x] 3.5 grep 校验：`Select-String -Path api\routes\commission_categories.py -Pattern "_ensure_commission_write_access"` 必须 0 命中
- [x] 3.6 错误 detail 复核：不含 "免费"/"专业"/"试用"/"trial"/字段名；grep 校验 `Select-String -Path api\routes\commission_categories.py -Pattern "专业版|免费版|trial|试用"` 必须 0 命中
- [x] 3.7 `python -m flake8 api/routes/commission_categories.py` 通过

## 4. 后端测试（T3）

- [x] 4.1 在 `tests/` 下新建 `test_commission_gating.py`，覆盖 4 个 case：
  1. `test_get_categories_returns_data_during_trial`：free + `trial_expires_at = int(time.time()) + 3600` + `trial_used=1` → GET 200，返回数组
  2. `test_get_categories_403_after_trial_expiry`：free + `trial_expires_at = int(time.time()) - 3600` + `trial_used=1` → GET 403，detail 不含 plan 标签
  3. `test_get_categories_200_for_professional`：`subscription_type = 'professional'` + `trial_used=0` → GET 200
  4. `test_get_categories_403_for_plain_free`：free + `trial_expires_at=0` + `trial_used=0` → GET 403
- [x] 4.2 测试 fixture 用 SQLAlchemy `await session.execute(update(User).where(User.id == uid).values(...))` 设置 trial_*；session.commit() 后再发请求
- [x] 4.3 `python -m pytest tests/test_commission_gating.py -v --tb=short` 全绿（4 passed）
- [x] 4.4 `python -m flake8 tests/test_commission_gating.py` 通过

## 5. 前端：authStore trial-aware（Wave 2，T5，依赖 T1）

- [x] 5.1 `frontend/src/stores/authStore.js` `buildPersistedUser`（line 39-63）白名单字段追加 4 个 trial_*：
  ```js
  trial_used: trial_used ?? 0,
  trial_started_at: trial_started_at ?? 0,
  trial_expires_at: trial_expires_at ?? 0,
  trial_plan_at_start: trial_plan_at_start ?? '',
  ```
- [x] 5.2 在 actions 段（line 199-220 附近）新增 `isInTrial()` selector：
  ```js
  isInTrial: () => {
    const u = get().user
    if (!u || typeof u.trial_expires_at !== 'number') return false
    return u.trial_expires_at > Math.floor(Date.now() / 1000)
  },
  ```
- [x] 5.3 改写 `hasProfessionalAccess`（line 216-220）：
  ```js
  hasProfessionalAccess: () => {
    if (get().isAdmin()) return true                          // admin 短路保留在最前
    const subscriptionType = get().getSubscriptionType()
    if (PROFESSIONAL_TIERS.includes(subscriptionType)) return true
    return get().isInTrial()                                  // trial overlay 兜底
  },
  ```
- [x] 5.4 grep 校验：`Select-String -Path frontend\src\stores\authStore.js -Pattern "trial_used|trial_expires_at|isInTrial"` 必须 ≥7 行（4 字段在 buildPersistedUser + isInTrial 定义 + hasProfessionalAccess 引用）

## 6. 前端：CommissionCategoriesPage 两处 fetch 守卫（Wave 3，T6，依赖 T5）

- [x] 6.1 顶部读取 `const canManage = useAuthStore(s => s.hasProfessionalAccess())`（如已存在则不重复声明）
- [x] 6.2 `useCallback fetchCategories`（line 44 起）函数体最开头加守卫：
  ```jsx
  if (!canManage) { setCategories([]); return }
  ```
  并把 `canManage` 加到 useCallback deps
- [x] 6.3 初始 `useEffect`（line 58 起）函数体最开头加同款守卫，把 `canManage` 加到 deps
- [x] 6.4 渲染段最顶部插入 `if (!canManage) return <UpgradePrompt title="此功能需要专业版" description="升级专业版/企业版后即可管理佣金类目；试用期内已新增的佣金规则将在升级后继续可用。" />`
- [x] 6.5 grep 校验：`Select-String -Path frontend\src\pages\CommissionCategoriesPage.jsx -Pattern "if \(!canManage\)"` 必须 ≥2 行

## 7. 前端：usePricingCalculation 两处 fetch 守卫（Wave 3，T7，依赖 T5）

- [x] 7.1 `frontend/src/pages/pricing/usePricingCalculation.js` 顶部 import 区追加 `import { useAuthStore } from '../../stores/authStore'`
- [x] 7.2 `refreshCommissionCategories`（line 39）函数体最开头加守卫：
  ```js
  if (!useAuthStore.getState().hasProfessionalAccess()) {
    setCommissionCategories([])
    return
  }
  ```
- [x] 7.3 初始 `useEffect`（line 61-84）改写 Promise.all：
  ```js
  const hasPro = useAuthStore.getState().hasProfessionalAccess()
  const commissionPromise = hasPro
    ? commissionCategoriesAPI.getAll()
    : Promise.resolve([])
  const [productData, commissionData] = await Promise.all([productsAPI.getAll(), commissionPromise])
  ```
- [x] 7.4 grep 校验：`Select-String -Path frontend\src\pages\pricing\usePricingCalculation.js -Pattern "hasProfessionalAccess"` 必须 ≥2 行

## 8. 前端测试（T8）

- [x] 8.1 `frontend/src/__tests__/authStore.trial.test.js` 新建，覆盖 3 case：
  1. `isInTrial()` 返回 true 当 `trial_expires_at > now`；返回 false 当过期/缺字段
  2. `hasProfessionalAccess()` 返回 true：(a) admin (b) PROFESSIONAL_TIERS 套餐 (c) free + trial 未过期；返回 false：free + trial 过期 + 非 admin
  3. `buildPersistedUser` 持久化 4 个 trial_* 字段（reload 后保留）
- [x] 8.2 `frontend/src/__tests__/CommissionCategoriesPage.test.jsx`（新建或加 case）：mock `hasProfessionalAccess=false` → render 后断言 `commissionCategoriesAPI.getAll` spy 0 次调用 + `<UpgradePrompt />` 出现
- [x] 8.3 `frontend/src/__tests__/usePricingCalculation.test.js`（新建或加 case）：mock `hasProfessionalAccess=false` → render hook 后断言 `commissionCategoriesAPI.getAll` spy 0 次调用，`commissionCategories` state = []
- [x] 8.4 `cd frontend && npm test -- --run` 全绿（0 failed）

## 9. Manual QA（Playwright MCP，T9，依赖 T1-T8 全绿）

- [x] 9.1 启动后端：按 AGENTS.md 模板设置 `ALLOWED_ORIGINS`/`E2E_TEST`/`E2E_DISABLE_NEW_LOGIN_SESSION_KICK`，`Start-Process` 后台启动 + 重定向 backend.log
- [x] 9.2 启动前端：`Start-Process npm run dev` 后台
- [x] 9.3 **安全双护栏**：先跑 `psql -h localhost -U postgres -d logistics_dev -c "\conninfo"`，确认 DB 名包含 `dev` 或 `test`；纯 `logistics` 生产名 → STOP
- [x] 9.4 准备 QA 账号 `qa-trial@cbprice.cn`（必须 `is_test_user=1`），初始 `trial_used=0`，`subscription_type='free'`
- [x] 9.5 用 qa_trial_user 登录前端 → 进入 `/commission-categories`，截图 `docs/qa/trial-commission-1-free-no-trial.png`：应显示 `UpgradePrompt`，无表格
- [x] 9.6 psql 模拟 Pro 试用激活：`UPDATE users SET trial_used=1, trial_started_at=EXTRACT(epoch FROM now())::int, trial_expires_at=EXTRACT(epoch FROM now())::int+604800, trial_plan_at_start='free' WHERE is_test_user=1 AND email='qa-trial@cbprice.cn'` → 用户重新登录或 hard refresh → 进入 `/commission-categories`，截图 `docs/qa/trial-commission-2-trial-active.png`：应显示完整管理表格 + `+ 新增` 按钮可点
- [x] 9.7 点 `+ 新增` → 输入 `QA测试类目` + 三档 5%/8%/12% → 保存，截图 `docs/qa/trial-commission-3-create-during-trial.png`
- [x] 9.8 编辑该行改名 `QA测试类目-edited` → 保存，截图 `docs/qa/trial-commission-4-edit-during-trial.png`
- [x] 9.9 psql 模拟过期：`UPDATE users SET trial_expires_at=EXTRACT(epoch FROM now())::int-3600 WHERE is_test_user=1 AND email='qa-trial@cbprice.cn'` → 刷新前端，截图 `docs/qa/trial-commission-5-trial-expired.png`：应回到 `UpgradePrompt`，浏览器网络面板**无** `/api/commission-categories` 请求
- [x] 9.10 psql 验证数据保留：`SELECT id, name, is_active FROM commission_categories WHERE user_id=(SELECT id FROM users WHERE email='qa-trial@cbprice.cn')` → 终端截图保存到 `docs/qa/trial-commission-6-data-preserved.txt`
- [x] 9.11 psql 模拟升级：`UPDATE users SET subscription_type='professional' WHERE is_test_user=1 AND email='qa-trial@cbprice.cn'` → 用户刷新 → `/commission-categories` 重新显示表格 + 历史数据完整，截图 `docs/qa/trial-commission-7-after-upgrade.png`
- [x] 9.12 打开 `/pricing` 切到精准模式 → 验证"佣金类目"下拉含历史类目可选，截图 `docs/qa/trial-commission-8-pricing-precise-selector.png`
- [x] 9.13 安全收尾：psql `UPDATE users SET trial_used=0, trial_started_at=0, trial_expires_at=0, trial_plan_at_start='', subscription_type='free' WHERE is_test_user=1 AND email='qa-trial@cbprice.cn'`；Remove-Item Env:PGPASSWORD
- [x] 9.14 关闭 backend / frontend 进程，归档 8 张截图

## 10. 收尾：lint + 全量测试 + commit + archive（T10）

- [x] 10.1 `python -m flake8 api services tests` 0 输出
- [x] 10.2 `python -m pytest --tb=line -q` 全绿，与 baseline 对齐（无新增失败）
- [x] 10.3 `cd frontend && npm test -- --run` 全绿
- [x] 10.4 同步更新 PLAN.md：把 Phase 26 当前任务指向本 OpenSpec change `fix-trial-aware-commission-gating`，列出关键产出文件
- [x] 10.5 git 分**两个原子 commit**：
  - **C1** `feat(api): expose trial fields and gate commission GET on effective plan`：包含 `api/models/schemas.py` + `api/dependencies.py` + `api/routes/auth.py` + `api/routes/commission_categories.py` + `tests/test_commission_gating.py` + OpenSpec artifacts + PLAN.md
  - **C2** `feat(frontend): trial-aware authStore and commission gates`：包含 `frontend/src/stores/authStore.js` + `frontend/src/pages/CommissionCategoriesPage.jsx` + `frontend/src/pages/pricing/usePricingCalculation.js` + 3 个新测试文件
- [x] 10.6 `openspec status fix-trial-aware-commission-gating` 确认 isComplete: true
- [x] 10.7 `openspec archive fix-trial-aware-commission-gating`（用户确认后）
