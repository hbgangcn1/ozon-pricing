## 1. Hook Fix (usePricingCalculation)

- [x] 1.1 在 `frontend/src/pages/pricing/usePricingCalculation.js` 引入 `useAuthStore`,在主数据 `useEffect`(line 65-89)开头加 `if (!user) return` 闸门
- [x] 1.2 将 `hasProfessionalAccess` 改为闸门通过后在 effect 内通过 `useAuthStore.getState().hasProfessionalAccess()` 求值,避免 stale closure
- [x] 1.3 主数据 effect 依赖数组追加 `user?.id, user?.subscription_type, user?.role`,保留原有 `refreshCommissionCategories, refreshProducts`
- [x] 1.4 同 effect 内加 `cancelled` 标志 + cleanup `return () => { cancelled = true }`,setState 前判 `!cancelled`,避免快速登出/切号写入旧数据
- [x] 1.5 审计 `checkLogistics` effect(line 97-118)是否有同类竞态;若有,按相同模式加 `if (!user) return` + cancellation,依赖加 `user?.id`
- [x] 1.6 本地 `npm run lint`(frontend),零 warning

## 2. Vitest 单元测试

- [x] 2.1 在 `frontend/src/__tests__/usePricingCalculation.test.jsx`(若不存在则新建)用 `@testing-library/react` `renderHook` 覆盖 4 场景
- [x] 2.2 场景 A:user=null 渲染时,`commissionCategoriesAPI.getAll` 不被调用,`commissionCategories` 保持初始 `[]`
- [x] 2.3 场景 B:initial null → user 注入(模拟 setAuth 后 commit),effect 重跑,`commissionCategoriesAPI.getAll` 被调用 1 次,state 更新为 mock 数据
- [x] 2.4 场景 C:professional user 直接挂载,fetch 触发,state 收到非空数组
- [x] 2.5 场景 D:基础订阅 user 挂载,`commissionCategoriesAPI.getAll` 不被调用,`commissionCategories` 保持 `[]`(权限闸门正确)
- [x] 2.6 `npx vitest run src/__tests__/usePricingCalculation.test.jsx`,4 个用例全绿

## 3. Playwright E2E

- [x] 3.1 新建 `frontend/tests/pricing/commission-categories-race.spec.js`(路径调整,挂载 chromium-no-auth project)
- [x] 3.2 测试 1:admin 登录 → 立即跳定价页 → 切精准模式 → 打开佣金类目下拉 → 断言含至少 1 个非"不使用类目"的 option
- [x] 3.3 测试 2:刷新页面 → 重复断言(防止只在持久化 user 后才 ok)
- [x] 3.4 凭据从 `frontend/tests/fixtures/test-data.js`(TEST_ADMIN)读取
- [x] 3.5 `npx playwright test tests/pricing/commission-categories-race.spec.js --project=chromium-no-auth --reporter=list --workers=1`,2 用例全绿(19.8s);**真因修复**:`api.js` `productsAPI.getAll` `limit:1000` → `200`(后端 cap `le=200` 导致 422 → `Promise.all` reject → 佣金 setState 跳过);`usePricingCalculation` 改用 `Promise.allSettled` 防御

## 4. 本地手动 QA

- [x] 4.1 用 `scripts/start_backend_detached.ps1` + `scripts/start_frontend_detached.ps1` 起服务(已运行:backend pid 43436, frontend pid 36064)
- [x] 4.2 浏览器登录 admin → 精准定价 → 截图佣金类目下拉,确认含"日化用品"(id=3562) → `01-precise-mode-commission-dropdown-open.png`
- [x] 4.3 跳过(无基础订阅测试号);Vitest 场景 D + admin 实际验证已覆盖权限闸门
- [x] 4.4 截图存证 `01-precise-mode-commission-dropdown-open.png` + `02-precise-mode-commission-selected.png`

## 5. 静态检查 + 全量回归

- [x] 5.1 `python -m flake8`(零错误,确认无后端误改)
- [x] 5.2 `npm run lint`(frontend,零警告)
- [x] 5.3 `npx vitest run`(frontend 全量,429/429 通过)
- [x] 5.4 `python -m pytest --tb=short`(后端全量,2477 通过 / 4 失败:`test_health_response_under_500ms` 是并行下 perf flake 已确认串行下通过;`test_e2e_volume_modes.py::*` 3 个失败属并发 worktree `fix-logistics-pool-batch-add-blackscreen` 任务范围,非本任务引入)

## 6. 部署上线

- [x] 6.1 `git add` + `git commit` 描述根因 + 修复 + 测试覆盖
- [x] 6.2 `git push origin main`
- [x] 6.3 SSH 拉代码:`ssh SSH_USER@SERVER_IP 'cd /var/www/ozon-pricing && git pull origin main 2>&1 | tail -5'`
- [x] 6.4 后台启动 deploy:`ssh SSH_USER@SERVER_IP 'cd /var/www/ozon-pricing && nohup bash deploy/deploy.sh > /tmp/deploy.log 2>&1 < /dev/null & disown; echo started'`
- [x] 6.5 `Start-Sleep -Seconds 30` 后跟日志:`ssh SSH_USER@SERVER_IP 'tail -30 /tmp/deploy.log'`,确认 deploy.sh 11 步全部通过

## 7. 线上回归

- [x] 7.1 公网健康:`(Invoke-WebRequest https://www.cbprice.cn/api/exchange/rates -TimeoutSec 10).StatusCode` = 200
- [x] 7.2 浏览器登录 https://www.cbprice.cn admin → 精准定价 → 佣金类目下拉含"日化用品"截图
- [x] 7.3 强刷 + 重新登录场景重测,确认无回归

## 8. 凭据维护

- [x] 8.1 更新 `.sisyphus/credentials.local.md` admin user_id 字段为 `159043`
