## Context

`services/plan_resolution.py` 是 trial overlay 的 SSoT（文件头自述："callers (pricing, logistics CRUD, scheduler) never need to special-case trial users"）。提供：

- `is_in_trial(user) -> bool`：纯时间判断 `int(time.time()) < trial_expires_at`，无后台依赖。
- `get_effective_plan(user) -> str`：trial 期内返回 `"professional"`，否则返回 stored `subscription_type`。
- `get_effective_logistics_limit(session, user) -> int`：先查 plans 表（admin 在"方案管理"动态设置），plans 表无对应行时退回 `_FALLBACK_LIMITS` 字典。`-1` = 无上限。

`subscription-feature-gating` spec Requirement「特性闸门基于 effective plan」已经声明所有门禁 SHALL 走这个 SSoT，并明确列出物流规则数量限制、定价计算入口、规则启用动作。

但实际仓里有 3 处违规：

| # | 文件 | 函数 | 现状 |
|---|---|---|---|
| 1 | `api/routes/logistics_pool.py:60-98` | `_get_user_subscription` + `_check_logistics_limit` | 直接 SQL 读 `subscription_type` + 硬编码 `{free:1, efficiency:3, professional:10, enterprise:-1}` |
| 2 | `api/routes/commission_categories.py:22` | 路由前置检查 | `if user.subscription_type not in COMMISSION_ALLOWED_TIERS` |
| 3 | `api/routes/pricing.py:201-206, 304-309` | 精准模式入口门禁（两处） | `if user.subscription_type in ("free","efficiency")` |

7 天到期回落机制（`scripts/trial_check.py` + systemd hourly timer）已正确：trial 过期后 `is_in_trial` 自动返回 False（纯时间判断），`get_effective_plan` 自动回到 stored subscription_type；timer 仅做"超额裁剪 + 开 48h 重选窗"的副作用，不动 `subscription_type` 字段。本次修复**不涉及** trial_check.py 与 overflow 机制。

## Goals / Non-Goals

**Goals:**
- 三处违规调用统一改走 `services.plan_resolution` SSoT。
- 用户报告的 bug（`robert_trial` 在物流池"全部添加"被拒）通过 Playwright 复验修复。
- 错误文案中性化（"已达到您当前方案的物流规则上限（N 条）"），不暴露内部 plan 标签或 trial 状态。
- 现有 `tests/test_logistics_pool_import_limit.py` 改写为通过 plan_resolution 路径 + seed plans 表，新增 trial-aware 用例覆盖关键 Scenario。

**Non-Goals:**
- 不动 `services/plan_resolution.py`、`scripts/trial_check.py`、`services/overflow_service.py`（已正确）。
- 不动 `_ensure_enterprise_excel_access`（产品规则：Excel 导入到物流池是 admin 功能，trial 不解锁）。
- 不动 `products.py:64 EXCEL_ALLOWED_TIERS`（产品规则：Excel 产品导入是企业版独占）。
- 不修改 trial 重选窗 UI 文案。
- 不引入新 capability。
- 不动 `tests/_db_isolation.py`、`tests/conftest.py`、根 `conftest.py`（D6 / D13 红线）。
- 不做 schema 变更 / 数据迁移 / 依赖升级。
- 不修改前端代码（仅展示后端 detail，文案变更对 UI 透明）。

## Decisions

### D1: Fix #1 错误文案中性化
**决定**: 把旧文案 "您的订阅等级（X版）最多只能添加 N 条物流规则" 改为中性 "已达到您当前方案的物流规则上限（N 条）"。

**理由**:
- 旧文案暴露 `subscription_type` 内部值（"免费版"/"专业版"），trial 用户看到困惑。
- 中性文案避免在错误消息里区分 trial vs 真实 plan，降低 UI 复杂度。
- 用户在边界确认中明确选择此方案。

**替代方案**:
- (a) 区分 trial：「专业版试用期内最多 N 条」——拒绝，泄露内部状态。
- (b) 保留旧文案但用 effective_plan——拒绝，"专业版"字样会让 trial 用户误以为已升级。

### D2: `limit == -1` 视为无上限
**决定**: Fix #1 的判断分支必须显式处理 `limit == -1` → 直接通过；`limit > 0` → 与 active count 比较。

**理由**:
- admin 在"方案管理"把专业版 logistics_limit 设为 -1（无上限），plans 表存 -1。
- `get_effective_logistics_limit` 返回 -1 时不能写成 `if active_count >= -1` 这种隐式 bug。
- 与 `_FALLBACK_LIMITS["enterprise"]=-1` 语义一致。

### D3: 用 `count_user_active_rules` 而非自己 SQL
**决定**: Fix #1 旧实现自己 SELECT COUNT 算用户当前规则数，必须替换为 `services.plan_resolution.count_user_active_rules(session, user_id)`。

**理由**:
- `subscription-feature-gating` spec Scenario「启用规则数量统计排除溢出禁用」明确：所有限额检查 SHALL 用 `count_user_active_rules`，因为它过滤 `is_active=1 AND disabled_by_overflow=0`。
- 旧实现可能未排除 `disabled_by_overflow=1` 行，导致 trial 过期裁剪后仍把超额规则算入限额。

### D4: Fix #2 复用现有 COMMISSION_ALLOWED_TIERS
**决定**: 不新增白名单常量；直接 `if get_effective_plan(user) not in COMMISSION_ALLOWED_TIERS`。

**理由**:
- `api/dependencies.py:19` 已定义 `COMMISSION_ALLOWED_TIERS = {"professional","enterprise","gratitude","test"}`。
- trial 期内 `get_effective_plan` 返回 `"professional"`，自动落在白名单内。

### D5: Fix #3 不修改 `decrement_user_calculations`
**决定**: 仅替换 pricing.py:201-206 与 304-309 两处入口门禁；其后的 `decrement_user_calculations` 调用本身已 trial-aware，不动。

**理由**:
- 入口门禁是 "免费/效率版禁用精准模式"；超出本次 bug fix 范围的就不动。
- 减少改动面 = 减少回归风险。

### D6: 测试改写策略 — seed plans 表
**决定**: `tests/test_logistics_pool_import_limit.py` 改写为：测试 fixture 内 seed plans 表（free=1, efficiency=3, professional=10, enterprise=-1, gratitude=-1），断言改用新中性文案；新增 3 个 trial-aware 用例。

**理由**:
- 用户在边界确认中选 "改写现有文件"。
- seed plans 表 = 走真实 plan_resolution 路径 = 测试与生产逻辑一致。
- 不引入 mock，避免漂移。

**新增用例**：
- `test_trial_user_free_plan_unlimited_within_trial`: subscription_type=free + trial_expires_at=future + plans.professional.logistics_limit=-1 → 添加 5 条都成功。
- `test_trial_user_falls_back_after_expiry`: subscription_type=free + trial_expires_at=past → quota 按 free=1 严格执行。
- `test_real_professional_user_uses_plans_table`: subscription_type=professional + plans.professional.logistics_limit=10 → 第 11 条被拒。

### D8: 附带清理 `_ensure_enterprise_excel_access` dead code
**决定**: 在本 change 内删除 `api/routes/logistics_pool.py::_ensure_enterprise_excel_access` 函数 + `import_logistics_pool` 中对它的调用 + 不再需要的 `user: dict = Depends(get_user_with_subscription)` 参数 + `EXCEL_ALLOWED_TIERS` / `get_user_with_subscription` 在该模块的 import。`api/dependencies.py:20` 的 `EXCEL_ALLOWED_TIERS` 常量本身保留（`api/routes/products.py:65` 仍真实使用）。不写新 spec delta（无对外行为变化）。

**理由**:
- `import_logistics_pool` 已挂 `Depends(require_admin)`：非 admin 在依赖层即被 403，永远到不了 `_ensure_enterprise_excel_access` 的 subscription 检查；admin 又被 `if user.role == "admin": return` 提前放行。函数体的 `if subscription_type not in EXCEL_ALLOWED_TIERS` 分支不可达。
- 函数名 + `EXCEL_ALLOWED_TIERS` 白名单制造"企业版可写公共物流池"的强烈误导（本次复盘的初版笔记就被骗，写出自相矛盾的内容）。
- Oracle 决议（bg_43dec17b 第 1 轮）：选 A（删 dead code），同时同步删 `Depends(get_user_with_subscription)` 与 import；不选 C（audit logging）。

**替代方案（rejected）**:
- (B) 把 `_ensure_enterprise_excel_access` 改 trial-aware 然后保留：拒绝。该路径根本到不了；改它制造另一种 dead code。
- (C) 保留并加 audit logging：拒绝。增加噪音 + 维护负担，且函数本身仍不可达。
- 保留 `user` 参数仅为日志/未来用：拒绝。YAGNI；需要时再加。

### D9: `require_admin` 装饰器化（Oracle 第 2 轮 Q1=YES）
**决定**: 把 `import_logistics_pool` 的 `admin: int = Depends(require_admin)` 函数参数改为路由装饰器 `dependencies=[Depends(require_admin)]` 形式：`@router.post("/import", dependencies=[Depends(require_admin)])`，签名删除 `admin` 参数（其返回值未在函数体内使用）。

**理由**:
- Oracle bg_43dec17b 第 2 轮 Q1=YES：装饰器形式语义更准确（"门禁"而非"取值"），且与 D8 的精神一致——把闸门下沉到路由层，函数体只关心业务。
- 与现有 FastAPI 实践一致（多处路由已用 `dependencies=[Depends(...)]`）。
- 不改变行为（依赖仍执行，403 仍抛出），仅 signature/装饰器位置变化。

### D10: 配套重写 `tests/test_logistics_pool_import.py`
**决定**:
- 删 `test_import_logistics_pool_returns_423_for_permission_error` 中 `app.dependency_overrides[dependencies.get_user_with_subscription] = ...` 行（dead override，函数已不再 depend on 它）。
- 重写 `test_import_logistics_pool_blocks_non_enterprise_admin` 为 `test_import_logistics_pool_blocks_non_admin`：不再 override `get_user_with_subscription`；改为 override `dependencies.require_admin` 抛 `HTTPException(403, detail="需要管理员权限")`，断言 endpoint 返回 403 + 该 detail。这保护"endpoint 真挂了管理员门禁"这一不变量（防止未来谁不小心摘掉装饰器）。

**理由**:
- 旧测试名称含 "non_enterprise_admin"，断言 `403 + "此功能需要企业版或更高订阅等级"`，这是 dead-code 路径的断言，删除后该测试会假阳性失败。
- Oracle bg_43dec17b 第 2 轮 Q2=Y：重写而非纯删——"endpoint 必须管理员才能调用" 是真不变量，需要 regression test 守护。
- 仅 mock `require_admin` 抛 403 即可验证装饰器/参数生效路径，不依赖真实 user 数据，符合现有测试风格。

### D7: 不改前端
**决定**: 前端 `LogisticsPoolPage.jsx` 不动。

**理由**:
- 前端仅 `toast.error(error.response.data.detail)`，文案变更对 UI 透明。
- 重选窗 UI 文案保持现有（用户决策）。

## Risks / Trade-offs

- **[Risk]** Fix #1 修改了用户可见错误文案，可能有外部脚本/客户端硬编码匹配旧文案 → **Mitigation**: 旧文案是面向人类的中文 toast，无外部 API 契约依赖；测试改写覆盖新文案断言，不留旧文案残留。
- **[Risk]** Fix #2 让 trial 用户解锁佣金品类管理，未来若产品规则变更（佣金限定真实专业版），会反向 bug → **Mitigation**: 在 spec Scenario 显式写明 "trial 期内 free 用户 SHALL 能访问佣金品类"，未来需变更走新 OpenSpec change。
- **[Risk]** 改写测试若漏掉 plans seed，会触发 `_FALLBACK_LIMITS` 路径，断言可能假阳性通过 → **Mitigation**: 新增 `test_real_professional_user_uses_plans_table` 显式验证 plans 表读取路径生效（断言专业版 limit=10 来自 seed 而非 fallback=10——通过设 plans 为非 fallback 值如 7 验证）。
- **[Trade-off]** 不修复 `_ensure_enterprise_excel_access` 与 `products.py:64`：trial 用户不能解锁 Excel 导入。这是产品规则要求（用户确认），不是技术限制。
- **[Risk]** Fix #1 与 `logistics-pool-batch-add` spec 已声明的 "endpoint MUST enforce the user's subscription logistics quota (`_check_logistics_limit`) BEFORE attempting any insert" 兼容 — quota 计算路径变更但调用顺序不变。

## Migration Plan

无 schema/数据迁移。部署即生效。

**Rollback**: `git revert` commit 即可恢复（无副作用、无数据写入）。

## Open Questions

无（用户已确认所有边界：错误文案 / 测试改写 / 重选窗文案 / scope = A+B+C）。
