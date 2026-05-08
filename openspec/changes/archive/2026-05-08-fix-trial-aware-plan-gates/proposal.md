## Why

`subscription-feature-gating` spec 第 32 行已明确：「所有依赖订阅级别决策的特性闸门 SHALL 基于 `services.plan_resolution.get_effective_plan(user)` 而非直接读 `users.subscription_type`」。但仓里实际有 3 处门禁绕过这个 SSoT，直接读 `user.subscription_type`，导致试用期内的 free/efficiency 用户被当成原始计划拒绝。

用户实测复现：账户 `robert_trial`（subscription_type=free，trial 进行中）在前端"全部添加到我的物流"被拒，提示「您的订阅等级（免费版）最多只能添加 1 条物流规则」。这直接违反 `subscription-feature-gating` 已声明的 Scenario「试用期内的免费用户创建第 N 条物流规则」（应允许）。

## What Changes

- **Fix #1（核心 bug）**: `api/routes/logistics_pool.py:60-98` 的 `_get_user_subscription` + `_check_logistics_limit` 替换为 `services.plan_resolution.get_effective_logistics_limit(session, user)` + `count_user_active_rules(session, user_id)`。删除硬编码 `{free:1, efficiency:3, professional:10, enterprise:-1}` 字典。错误文案改为中性："已达到您当前方案的物流规则上限（N 条）"。受影响端点：`POST /api/logistics-pool/{id}/add-to-my-logistics`、`POST /api/logistics-pool/batch-add-to-my-logistics`。
- **Fix #2**: `api/routes/commission_categories.py:22` 的 `if user.subscription_type not in COMMISSION_ALLOWED_TIERS` 替换为 `if get_effective_plan(user) not in COMMISSION_ALLOWED_TIERS`。佣金品类是专业版功能，trial 期内应解锁。
- **Fix #3**: `api/routes/pricing.py:201-206` 与 `304-309` 两处精准模式入口门禁，把直接读 `user.subscription_type in ("free","efficiency")` 替换为 `get_effective_plan(user) in ("free","efficiency")`。
- **测试改写**: `tests/test_logistics_pool_import_limit.py` 现有 4 处硬编码旧文案断言 + 假设 free=1/professional=10。改写为：seed plans 表 + 通过 plan_resolution 路径断言新中性文案；新增 trial-aware 用例（subscription_type=free + trial_expires_at=future → 享受 professional limit；trial_expires_at=past → 退回 free limit；plans.professional.logistics_limit=-1 → 无上限）。
- **附带 dead-code 清理**（探查 plan 闸门时发现）: `api/routes/logistics_pool.py::import_logistics_pool` 的 `_ensure_enterprise_excel_access(user)` 是 dead code —— 同一函数挂了 `Depends(require_admin)`，非 admin 在依赖层就被 403，函数体永远到不了 `_ensure_enterprise_excel_access` 的 subscription 检查；admin 又会被该函数的 `if user.role == "admin": return` 提前放行。但函数名 + `EXCEL_ALLOWED_TIERS` 白名单制造"企业版可写公共物流池"的强烈误导（连本次复盘都被骗，写出自相矛盾的笔记）。Oracle 决议：删 dead code（方向 A）+ 把 `Depends(require_admin)` 移到装饰器层 + 删除随之无用的 `user` 参数与 `get_user_with_subscription` import + 删除 `EXCEL_ALLOWED_TIERS` 在 logistics_pool.py 的 import。`EXCEL_ALLOWED_TIERS` 常量本身保留（products.py 的真闸门仍在用）。配套重写 `tests/test_logistics_pool_import.py` 中两个测试。

**保持不动**（产品规则确认）:
- `api/routes/products.py:64 EXCEL_ALLOWED_TIERS`：Excel 产品导入是企业版独占，trial（=professional）不应解锁。
- `services/plan_resolution.py`、`scripts/trial_check.py`、`services/overflow_service.py`：SSoT 与 7 天到期回落机制本身已正确，不动。
- `tests/_db_isolation.py`、`tests/conftest.py`、根 `conftest.py`（D6/D13 红线）。

## Capabilities

### New Capabilities
（无新增 capability — 本次是 bug fix，修复实现未达成已声明 spec 的违规。）

### Modified Capabilities
- `subscription-feature-gating`: 在 Requirement「特性闸门基于 effective plan」下补充三个违规点的具体 Scenario（logistics-pool 批量添加、佣金品类访问、精准模式入口），并新增 Requirement 约束错误文案不暴露内部 plan 标签。
- `logistics-pool-batch-add`: 在 Requirement「Batch add public pool entries to user logistics」下明确 `_check_logistics_limit` 的 quota 解析 SHALL 走 `get_effective_logistics_limit`；明确 quota 错误文案为中性 "已达到您当前方案的物流规则上限（N 条）"；明确 `limit == -1` 时不施加上限。

## Impact

- **代码**: 3 个 Python 文件（`api/routes/logistics_pool.py`、`api/routes/commission_categories.py`、`api/routes/pricing.py`）+ 1 个测试文件改写（`tests/test_logistics_pool_import_limit.py`）。
- **API 行为**: 受影响端点的 quota 错误文案变更（旧："您的订阅等级（X版）最多只能添加 N 条物流规则" → 新："已达到您当前方案的物流规则上限（N 条）"）。试用期内 free/efficiency 用户原本被拒的请求现在会成功（这是 bug 修复，恢复 spec 已声明的正确行为）。
- **数据库**: 无 schema 变更。无迁移。
- **依赖**: 无新增依赖。
- **前端**: 无前端改动（前端仅展示后端返回的错误 detail；文案变更对 UI 透明）。
- **Playwright 验证路径**: 用 `robert_trial` 登录 → 公共物流池 → "全部添加到我的物流" → 期望成功（plans.professional.logistics_limit 当前 = -1 = 无上限）。
- **回归风险**: 真实 free/efficiency/professional/enterprise 用户的行为不变（plan_resolution 在非 trial 期返回 stored subscription_type）。
