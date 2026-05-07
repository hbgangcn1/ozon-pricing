# trial-overflow-scheduler Specification

## Purpose
TBD - created by archiving change add-pro-trial-overflow. Update Purpose after archive.
## Requirements
### Requirement: trial_check CLI 脚本

系统 SHALL 提供 `python -m scripts.trial_check` CLI,作为试用过期与 48h 窗口过期的扫描入口。脚本 SHALL 是幂等的(重复执行不会重复裁剪、不会重复开窗、不会重复关窗),SHALL 支持 `--once`(只跑一次后退出,默认行为)与 `--dry-run`(只输出计划动作不写库)参数。脚本 SHALL 对每个待处理用户使用 `SELECT ... FOR UPDATE SKIP LOCKED` 避免与 API 路径并发冲突。

#### Scenario: 处理过期试用并触发裁剪
- **WHEN** 脚本运行时存在 `trial_expires_at > 0 AND trial_expires_at <= now AND trial_plan_at_start <> ''` 的用户(`trial_plan_at_start <> ''` 是"该试用尚未被处理"的事实标记),且其启用规则数超出真实套餐限额
- **THEN** 脚本调用 `overflow_service.auto_trim_user_rules(user_id, effective_limit)` 执行裁剪与开窗(**不**调用 `apply_subscription_change`,因为 `subscription_type` 在试用期内始终未变),并在同一事务内将 `trial_plan_at_start = ''` 作为"已处理"标记写入

#### Scenario: 处理过期试用但无需裁剪
- **WHEN** 脚本检测到 `trial_expires_at <= now AND trial_plan_at_start <> ''` 的用户,但其启用规则数 ≤ 真实套餐限额
- **THEN** 脚本不执行裁剪、不开窗,但仍将 `trial_plan_at_start = ''` 写入,作为"已处理"标记防止重复扫描

#### Scenario: 关闭过期窗口
- **WHEN** 脚本运行时存在 `trial_overflow_window.closed_at = 0 AND expires_at < now` 的窗口
- **THEN** 脚本将其 `closed_at = now, close_reason = 'expired'`

#### Scenario: 重复执行幂等
- **WHEN** 同一脚本进程在 1 分钟内被调用两次
- **THEN** 第二次调用所选用户集合为空(因为第一次已将 `trial_plan_at_start` 清空),所选窗口集合也为空(因为第一次已关闭),不重复裁剪、不重复开窗、不重复关窗;所有数值状态与单次调用一致

#### Scenario: dry-run 不写库
- **WHEN** 以 `--dry-run` 参数调用脚本
- **THEN** 脚本只在日志中输出"将会发生的动作",数据库无任何变更

### Requirement: systemd timer 单实例触发

部署 SHALL 通过 systemd timer (`deploy/trial-check.timer`) 每小时触发一次 `deploy/trial-check.service`,后者执行 `python -m scripts.trial_check`。`deploy/deploy.sh` SHALL 安装并 `systemctl enable --now trial-check.timer`,并验证 timer 处于 active 状态。SHALL NOT 通过 FastAPI lifespan 启动该任务(避免 gunicorn `-w 3` 下重复执行)。

#### Scenario: 部署后 timer 处于 active
- **WHEN** `deploy/deploy.sh` 完成
- **THEN** `systemctl is-active trial-check.timer` 返回 `active`,且 `systemctl is-enabled trial-check.timer` 返回 `enabled`

#### Scenario: 不在 lifespan 启动后台调度
- **WHEN** FastAPI 应用启动
- **THEN** `api/main.py` 的 lifespan 不创建任何用于试用 / 窗口扫描的 asyncio task 或线程

#### Scenario: timer 间隔为小时级
- **WHEN** 检查 `deploy/trial-check.timer`
- **THEN** `OnCalendar` 或 `OnUnitActiveSec` 配置为每小时一次(允许 60 分钟容差)

### Requirement: 业务逻辑共享

`scripts/trial_check.py` SHALL NOT 内联裁剪 / 关窗 / 升级恢复的业务逻辑,而是调用 `services/trial_service.py` 与 `services/overflow_service.py` 中的 helper。同一组 helper SHALL 被 API 路由(试用领取、重新选择、升级回调)与 CLI 共享,确保单一事实来源。

#### Scenario: CLI 与 API 共享自动裁剪 helper
- **WHEN** 通过 CLI 触发的过期裁剪与通过 `apply_subscription_change` 触发的降级裁剪
- **THEN** 两者调用同一个 helper(例如 `overflow_service.auto_trim_user_rules(...)`),输入相同 user_id 时产生相同 DB 状态变更

