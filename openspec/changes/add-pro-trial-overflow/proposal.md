## Why

Free 与效率版用户没有低成本路径体验专业版的"无限物流规则"等高级能力,影响转化;同时当套餐降级或试用结束时,系统目前没有"超额规则"处置机制,用户会无声触发限额错误或导致定价行为不可预期。需要一次性引入"7 天专业版试用 + 物流规则溢出处理"来覆盖体验、留存、降级安全三个目标。

## What Changes

- 新增"7 天专业版试用"能力:每个用户终身仅可领取一次,试用期内拥有专业版权限(无限物流规则等),不修改 `users.subscription_type`,通过新增的试用状态字段判定有效套餐。
- 新增"物流规则溢出处理"能力:试用结束或套餐降级后,若用户启用规则数 > 真实套餐限额,系统在 T+0 自动按"最近使用"裁剪保留 N 条,其余规则被标记为 `disabled_by_overflow=1`。用户在此后 48h 窗口内可手动改选保留哪些。窗口结束后保留当前自动选择,窗口本身关闭。
- 新增"升级恢复"机制:用户升级到 professional/enterprise 时,自动清零 `disabled_by_overflow`,恢复所有被溢出禁用的规则,并解决任何未关闭的溢出窗口。
- **BREAKING(内部约束)**:所有订阅状态变更必须经由 `db/subscriptions.py` 的统一函数;禁止任何代码直接写 `User.subscription_type`(支付回调、admin 后台、CLI 全部统一)。
- 新增 logistics 字段 `disabled_by_overflow INTEGER NOT NULL DEFAULT 0` 和 `last_used_at INTEGER NOT NULL DEFAULT 0`(epoch seconds)。所有 pricing 查询过滤条件改为 `is_active == 1 AND disabled_by_overflow == 0`。
- 新增 users 字段 `trial_used`、`trial_started_at`、`trial_expires_at`、`trial_plan_at_start`(integer epoch / int)。
- 新增小时级后台任务:由 systemd timer 调用 `python -m scripts.trial_check`,处理试用过期、自动裁剪、48h 窗口过期。生产 gunicorn `-w 3` 下不在 FastAPI lifespan 内执行,避免 3 倍重复处理。
- 新增前端体验:试用倒计时横幅、试用结束/即将过期提示弹窗、48h 窗口内"重新选择保留规则"模态、被溢出禁用规则的灰色态展示。无后端推送通道。

## Capabilities

### New Capabilities
- `pro-trial`: 7 天专业版试用的领取、生效判定、过期处理与一次性约束。
- `logistics-overflow`: 试用结束或套餐降级后,物流规则超限时的自动裁剪、48h 重新选择窗口、升级恢复语义。
- `trial-overflow-scheduler`: 跨进程安全的小时级扫描任务,负责试用过期与窗口过期处理(systemd timer + 幂等脚本)。

### Modified Capabilities
- `subscription-feature-gating`: 新增"有效套餐(effective_plan)"概念——试用期内有效套餐为 professional,真实订阅 free/efficiency 不变;所有特性闸门改读有效套餐;增加 logistics 规则数量限额按"启用且未被溢出禁用"的口径计算。
- `plan-management-api`: 新增试用领取接口、试用状态查询接口、48h 窗口内重新选择保留规则的接口、当前溢出状态查询接口。
- `payment-api`: 升级成功路径必须通过 `db/subscriptions` chokepoint,触发"清零 `disabled_by_overflow` + 关闭未解决溢出窗口"的恢复事务。

## Impact

- **数据库**:`logistics` 表新增 2 列;`users` 表新增 4 列;新增 `trial_overflow_window`(或等价)记录表跟踪未关闭窗口与首次进入溢出的时间。Alembic 迁移 + `scripts/check_schema_integrity.py` `EXPECTED_CHECK_VALUES` 同步。
- **后端代码**:
  - `pricing/` 路径所有 active 规则查询统一加 `disabled_by_overflow == 0` 过滤(至少 `api/routes/_pricing_helpers.py`)。
  - 新增 `services/trial_service.py` 与 `services/overflow_service.py`(试用领取/状态、自动裁剪、窗口管理、升级恢复 helper)。
  - 新增 `db/subscriptions.apply_subscription_change(...)` 统一 chokepoint;`payment_handler.py`、`payment_callback_enhanced.py`、`services/payment_service.py`、admin 路径全部改走它。
  - 新增 `api/routes/trial.py`(或并入 `subscriptions.py`)暴露试用领取、状态、重新选择接口。
  - 新增 `scripts/trial_check.py` CLI(幂等,可重复执行)。
  - pricing API 在最终结果产出后调用 `mark_logistics_used(user_id, winner_rule_ids, now)`,一次批量 UPDATE `last_used_at`(节流条件 `last_used_at < now - 60`),不在候选过滤、SSE progress、breakeven 辅助计算中写库。
- **部署**:`deploy/` 新增 `trial-check.service` + `trial-check.timer`;`deploy/deploy.sh` 安装并启用 timer;新增 schema CHECK 不变量(若适用)进 `scripts/check_schema_integrity.py`。
- **前端**:试用横幅、试用过期/即将过期模态、48h 重新选择模态、规则列表灰色禁用态、试用领取按钮(仅 `trial_used=false` 且套餐为 free/efficiency 时可见)。
- **测试**:试用领取幂等与一次性、有效套餐判定矩阵、自动裁剪正确性(MRU 排序与零使用回退)、48h 窗口流转、升级恢复幂等、`trial_check` CLI 幂等、systemd timer 启动验证、所有 pricing 路径过滤生效。
- **独立风险记录**:`postgres_backup_service.py` 在 gunicorn `-w 3` 下没有跨进程锁,会被三个 worker 各启动一次自动备份线程。本变更不修复,但应另开任务处理。
