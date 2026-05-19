## Context

系统已有完整的试用机制（`services/trial_service.py` + `services/plan_resolution.py`）：
- `claim_trial()` 原子性领取试用，设置 `trial_expires_at = now + 7*86400`，但**永不修改** `subscription_type`（仍为 `"free"`）。
- `get_effective_plan(user)` 已正确实现 trial overlay：试用期间返回 `"professional"`，过期后回退到原套餐。
- 精准模式门控（`api/routes/pricing.py` line 220）和物流规则限额（`services/plan_resolution.py:get_effective_logistics_limit()`）都已使用 `get_effective_plan()`，trial-aware。

**缺失环节**：`db/subscription_quota.py:decrement_user_calculations()` 是计算次数限制的唯一检查点，但它只读取 `subscription_type` / `user_type`，完全不检查 `trial_expires_at`。因此试用期间用户被当成 `"free"` 处理，`remaining_calculations` 被扣减至 0 后触发 403。

## Goals / Non-Goals

**Goals:**
- 试用期间用户计算次数不受限制，与真实 `"professional"` 用户一致。
- 试用过期后自动回到原套餐的限制逻辑（如 `"free"` 则恢复 10 次/日限制）。
- 逻辑修复覆盖 `/calculate` 与 `/calculate-grouped` 两个入口。
- 测试覆盖试用中、试用过期、真实 professional 三种场景。

**Non-Goals:**
- 不修改前端（前端 `authStore.hasProfessionalAccess()` 已正确）。
- 不修改 API 接口签名或响应结构。
- 不修改数据库 schema。
- 不改动 `get_effective_plan()` 本身（它已正确）。

## Decisions

### Decision 1: 修复位置选 `decrement_user_calculations` 而非 `pricing.py`

**选项 A**：在 `pricing.py` 的两次调用前增加 `if is_in_trial(user): skip decrement`。
- 优点：改动最小，只影响 pricing 路由。
- 缺点：如果有第三个计算入口（未来新增），容易遗漏；职责分散。

**选项 B**：在 `decrement_user_calculations` 内部引入 trial 判断。
- 优点： Single source of truth。所有计算次数扣减统一走这里，未来新增入口无需重复判断。
- 缺点：需要导入 `services.plan_resolution`，但 `db/` 包目前不依赖 `services/`（已有 `db/plans` 依赖，无循环导入风险）。

**选择 B**。`db/subscription_quota.py` 已经通过 `_patched_get_plan_by_code()` 做了跨模块引用，再导入 `is_in_trial` 不会引入新的循环依赖。`services/plan_resolution` 是纯函数模块，无外部 I/O。

### Decision 2: 使用 `get_effective_plan()` 而非直接 `is_in_trial()`

`decrement_user_calculations` 当前按 plan code 白名单放行：
```python
if user_type in ["admin", "permanent", "enterprise", ...]:
    return True
```

如果仅加 `if is_in_trial(user): return True`，虽然能修复 trial，但无法享受 `get_effective_plan()` 的统一语义（例如未来 trial 过期后回退逻辑变化，只需改一处）。

**选择**：将原有 `user_type` 读取逻辑替换为 `effective_plan = get_effective_plan(user)`，再按 effective_plan 白名单判断。这样：
- trial 中 → `professional` → 放行
- trial 过期 → 回退到 `trial_plan_at_start`（通常为 `"free"`）→ 进入限制逻辑
- 与精准模式门控完全一致

### Decision 3: `reset_user_daily_calculations` 同步修复

`reset_user_daily_calculations()` 在登录时按 plan 的 `calc_limit` 重置 `remaining_calculations`。试用中的用户如果 `calc_limit != -1`，会被重置为有限次数。

虽然 `decrement_user_calculations` 修复后，即使 `remaining_calculations` 被重置为有限值，试用期间也不会被限制（因为先检查 trial），但这会造成数据不一致：试用期间 `remaining_calculations` 显示为 10（或某个有限值），而实际无限。

**选择**：在 `reset_user_daily_calculations` 中也引入 `is_in_trial` 判断：试用中直接返回 `False`（跳过重置），保持 `remaining_calculations` 原值不变。

## Risks / Trade-offs

- **[Risk] `get_effective_plan` 引入 `services` 依赖到 `db/` 包** → 当前 `services/plan_resolution` 是纯函数模块，不依赖 `db/`；`db/subscription_quota.py` 已有 `_patched_get_plan_by_code()` 引用 `db.plans`，无循环风险。Mitigation: 确认 `services.plan_resolution` import 后运行 `python -m pytest` 无 ImportError。
- **[Risk] `get_effective_plan` 在 `decrement_user_calculations` 中增加同步计算开销** → 该函数是纯函数，仅做 `int()` 转换和 `time.time()` 比较，耗时 < 1μs，可忽略。
- **[Risk] 现有测试假设 free 用户一定被限制** → 需要更新/新增测试覆盖 trial 场景。Mitigation: 新增 `test_subscription_quota_trial.py`，不改动现有通过的测试。
- **[Trade-off] `reset_user_daily_calculations` 跳过 trial 用户后，`remaining_calculations` 可能长期保持旧值** → 试用过期后下一次登录会正常重置，无影响。

## Migration Plan

无需迁移。无 schema 变更，无数据迁移。部署即生效。

Rollback: 回退 `db/subscription_quota.py` 单文件即可。

## Open Questions

无。
