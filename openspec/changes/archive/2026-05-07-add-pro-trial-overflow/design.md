## Context

当前订阅模型(免费 1 条 / 效率 3 条 / 专业·企业无限物流规则)对升级转化和降级安全都不友好:

- 免费/效率版用户没有低成本试用专业版的路径,转化漏斗薄;
- 一旦降级或试用结束,系统对"超额规则"没有处置策略,要么静默允许超额,要么用户在使用中突然被限额报错;
- 历史 SQLite→PostgreSQL 类型残留(见 `AGENTS.md` "数据库 schema 完整性"章节)使任何新增列都需要同步 `scripts/check_schema_integrity.py`;
- 生产是 gunicorn `-w 3` UvicornWorker,任何在 FastAPI lifespan 中启动的后台任务会在 3 个 worker 各运行一次。已知 `postgres_backup_service.py` 即受此影响(独立 bug,本变更只记录、不修复)。

利益相关方:产品(转化与体验)、后端(数据模型/调度安全)、前端(试用与溢出体验)、运维(systemd 部署 + schema 守卫)。

## Goals / Non-Goals

**Goals:**
- 每用户终身一次的 7 天专业版试用,试用期内享受专业版能力(无限物流规则等),零真实订阅状态变更。
- 试用结束 / 套餐降级时,自动按"最近使用"裁剪保留 N 条物流规则,其余规则被"溢出禁用"(`disabled_by_overflow=1`)且对用户可见(灰色态)。
- 48h 重新选择窗口:用户可在窗口内手动改选保留的 N 条;窗口结束保留当前自动选择,窗口关闭。
- 升级到 professional / enterprise 后,所有 `disabled_by_overflow` 规则一次性恢复,所有未关闭窗口被解决。
- 跨进程安全的小时级扫描:试用过期 + 窗口过期由 systemd timer 单实例触发,不依赖 lifespan。
- 订阅状态变更的单一 chokepoint:`db/subscriptions.apply_subscription_change(...)`,所有路径(支付回调、admin、CLI)统一调用。

**Non-Goals:**
- 不引入服务端推送 / 站内信 / 邮件通知;通知完全靠前端横幅 + 弹窗 + 状态查询接口。
- 不修复 `postgres_backup_service.py` 的多 worker 重复执行 bug(独立任务)。
- 不重构 `is_active` 语义、不引入 status 枚举(沿用现有 boolean,新增 `disabled_by_overflow` 旁列)。
- 不引入 APScheduler 等新调度库依赖。
- 不重构 `pricing/` 模块为有状态;`select_best.py` 等保持纯函数,DB 写入只在 API/service 层完成。
- 不改 `users.subscription_type` 取值集合;`free / efficiency / professional / enterprise` 不变。

## Decisions

> 以下 6 项关键技术决策由 Oracle 在 `AGENTS.md` 授权的"纯技术问题"范围内裁定。每项均给出选项与拒选理由。

### Decision 1: Logistics 溢出禁用列设计 — 旁列 `disabled_by_overflow`(option C)

新增 `Logistics.disabled_by_overflow INTEGER NOT NULL DEFAULT 0`,与现有 `is_active` 并列。pricing 与启用计数统一过滤 `is_active == 1 AND disabled_by_overflow == 0`。

- 拒选 A(新增 `status` 枚举):需要重写所有 pricing 过滤路径,迁移风险大,且与现有 `is_active` 语义重合。
- 拒选 B(`disabled_reason` 枚举):语义混合两类禁用,升级恢复时需判断 reason,容易误恢复用户手动禁用项。
- 选 C 收益:升级恢复只需 `UPDATE ... SET disabled_by_overflow = 0`,天然不会触碰用户手动禁用;48h 窗口内"切换保留集"也只是翻这一列。
- 可选附加 `overflow_disabled_at INTEGER NULL`(epoch)供 UI 显示"何时被限额禁用",非必需,实现阶段决定。

### Decision 2: 试用状态字段位置 — 放在 `users` 表(option A)

在 `users` 表新增 4 个字段(全部沿用项目惯例 epoch seconds 整数 / 整数布尔):

- `trial_used INTEGER NOT NULL DEFAULT 0`
- `trial_started_at INTEGER NOT NULL DEFAULT 0`
- `trial_expires_at INTEGER NOT NULL DEFAULT 0`
- `trial_plan_at_start TEXT NOT NULL DEFAULT ''`(领取试用时的真实 `subscription_type`,过期处置时使用)

`is_in_trial(user)` = `trial_expires_at > now AND subscription_type IN ('free','efficiency')`。**绝不修改 `subscription_type`**。

- 拒选 B(独立 `user_trials` 表):每次 pricing 都要 join,收益不抵成本。
- 拒选 C(写入 subscriptions 表):违反"试用不修改订阅状态"业务规则,污染计费数据。

### Decision 3: 调度机制 — systemd timer + `python -m scripts.trial_check`(option C)

- 拒选 A(lifespan + asyncio + advisory lock):3 个 worker 各开一份循环,只是抢锁不真正并发执行;增加无谓 CPU 与连接占用,且 lifespan 与 worker 生命周期耦合。
- 拒选 B(APScheduler):新增依赖,违反"无新调度依赖"目标。
- 拒选 D(每请求 lazy 检查):溢出处理是大事务,放在请求路径上影响 P99,且不能驱动 48h 窗口过期。
- 拒选 E(沿用 `postgres_backup_service.py` 的 thread+schedule):该模式本身在 `-w 3` 下重复执行,不该再复制。
- 选 C:systemd 单实例触发,与 worker 解耦,失败重试由 timer 控制;脚本本身幂等。

部署集成:`deploy/trial-check.service` + `deploy/trial-check.timer`,在 `deploy/deploy.sh` 安装并 `systemctl enable --now trial-check.timer`。

### Decision 4: 订阅升级回调 — `db/subscriptions.apply_subscription_change(...)` chokepoint(option B)

- 拒选 A(挂支付回调):漏掉 admin 手动升级与未来其他升级路径。
- 拒选 C(SQLAlchemy event listener):项目中无现存 event listener 用法,与 async session 配合复杂,可读性差。
- 拒选 D(domain event/pubsub):基础设施未具备,过度设计。
- 选 B:收敛所有写 `subscription_type` 的路径到一个函数。函数职责:
  1. 在事务内更新订阅字段;
  2. 若新套餐为 `professional` / `enterprise`,执行恢复事务(`disabled_by_overflow = 0`、关闭未解决窗口、记录恢复事件);
  3. 幂等(再次调用同样套餐切换不重复处理)。

所有现存写订阅的位置(`payment_handler.py`、`payment_callback_enhanced.py`、`services/payment_service.py`、admin 路径)改走该函数。

### Decision 5: MRU 数据源 — 新增 `last_used_at INTEGER`,pricing 后批量同步写(option A)

- 拒选 B(BackgroundTasks 异步写):跨 session 复杂、流式响应/进程重启场景下可丢。
- 拒选 C(`updated_at` 代理):`models/logistics.py` 当前没有 `updated_at`,且"编辑"≠"使用"。
- 拒选 D(`id DESC`):无法反映"老规则但日常使用"。
- 拒选 E(`usage_count + last_used_at`):auto-trim 只需排序,加 count 是过度设计。
- 选 A 实现细节:
  - 新增 `Logistics.last_used_at INTEGER NOT NULL DEFAULT 0`(epoch seconds)。
  - auto-trim 排序键:`ORDER BY last_used_at DESC, id DESC`(零使用历史回退到创建顺序)。
  - 写入语句:`UPDATE logistics SET last_used_at = :now WHERE user_id = :uid AND id IN (:winners) AND last_used_at < :now - 60`(60 秒节流,降低热点写)。
  - 写入位置:**API/service 层在 pricing 完成、最终结果产出后**;`pricing/select_best.py` 等纯函数模块**禁止**写库。

### Decision 6: "use" 的定义 — 仅最终入选 winner(option A)

- 拒选 B(进入候选集即算 use):一次定价请求会写多条规则,与 SSE 多 progress 事件叠加放大写入。
- 拒选 C(包含手动编辑):污染语义,编辑 ≠ 使用。
- 拒选 D(deferred):决策已具备充分信息,不延后。
- 选 A 实现细节:
  - 收集 `/api/pricing/calculate` 最终响应中正常展示给用户的所有 winner ID(低价优先 / 速度优先 / land / air 等多目标 winner 都算),去重后一次批量 UPDATE。
  - **排除**候选集、淘汰列表、breakeven 辅助计算、SSE 中间 progress 事件中的 ID。
  - helper:`mark_logistics_used(session, user_id, rule_ids: set[int], now: int) -> None`。

### Cross-cutting decision: Effective plan helper

新增 `services/plan_resolution.py`(或 `services/trial_service.py`):

- `get_effective_plan(user) -> str`:试用未过期且真实套餐 ∈ {free, efficiency} → 返回 `professional`;否则返回真实 `subscription_type`。
- `get_effective_logistics_limit(user) -> int`:基于 `get_effective_plan` 查询 `plans` 表 `logistics_limit`(-1 表示无限)。
- `count_user_active_rules(session, user_id) -> int`:`SELECT COUNT(*) WHERE user_id=? AND is_active=1 AND disabled_by_overflow=0`。

特性闸门(`subscription-feature-gating`)、CRUD 创建检查、auto-trim、前端状态查询接口必须共享同一组 helper,杜绝"试用中和试用后限额计算不一致"。

### Cross-cutting decision: Overflow window 数据结构

新增表 `trial_overflow_window`(命名最终化在实现阶段确认):

- `id`, `user_id`, `opened_at INTEGER`, `expires_at INTEGER`(opened_at + 48h), `closed_at INTEGER NOT NULL DEFAULT 0`, `close_reason TEXT`(枚举:`expired` / `upgraded` / `reselected`)
- 唯一约束:同一 user 同时只能有一个 `closed_at = 0` 的记录(避免重复开窗)。
- 升级恢复必须将该用户所有 `closed_at = 0` 的窗口标记为 `closed_at = now, close_reason = 'upgraded'`。
- 48h 过期处理同样置 `close_reason = 'expired'`,**不再二次裁剪**(裁剪在窗口开启时已完成)。

## Risks / Trade-offs

- **风险:pricing 路径漏过滤 `disabled_by_overflow`** → 缓解:实现阶段建立单一查询 helper(如 `get_user_active_logistics(session, user_id)`),所有 pricing 入口必须通过它;CI 添加 grep 测试禁止裸写 `is_active == 1` 而不带 overflow 过滤。
- **风险:`trial_used` 并发领取导致重复试用** → 缓解:领取接口使用条件 UPDATE `WHERE trial_used = 0`,RowCount 检查;失败返回 409。
- **风险:绕过 `apply_subscription_change` 直接写 `User.subscription_type`** → 缓解:在 `db/subscriptions.py` 顶部强注释禁止;`tests/` 增加单测断言所有现有 payment / admin 路径都经过 chokepoint;代码评审强制项。
- **风险:systemd timer 与 deploy.sh 集成失败导致后台任务静默不跑** → 缓解:deploy.sh 安装后立即 `systemctl is-active trial-check.timer` 校验;脚本支持 `--once` 参数,部署时手动跑一次冒烟。
- **风险:`scripts.trial_check` 与 API 同时尝试改某用户(竞态)** → 缓解:脚本对每个待处理用户使用 `SELECT ... FOR UPDATE SKIP LOCKED`,API 升级路径走 `apply_subscription_change` 自带事务。
- **风险:MRU 写入热点(同一规则被高频选中)** → 缓解:60 秒节流条件 `last_used_at < now - 60`。
- **风险:`scripts/check_schema_integrity.py` 漏更新导致部署中止** → 缓解:实现阶段同步追加 `EXPECTED_CHECK_VALUES`(若新增 CHECK 约束);本变更主要新增列与默认值,预计无新 CHECK,但实现阶段必须明确确认。
- **风险:前端横幅/模态过度打扰用户** → 缓解:横幅 dismiss 24h 内不重显;48h 重新选择模态首次进入溢出态时弹一次,后续仅在用户主动进入物流规则页面时提示。
- **风险:试用过期瞬间 N=1 用户被裁掉唯一日常用规则**(因为零使用记录回退到 `id DESC`,新建的可能不是常用的) → 缓解:文档中明确"建议用户在试用期内至少使用一次想保留的规则";48h 窗口给用户兜底重选能力。

## Migration Plan

1. **Alembic 迁移**(单一 revision):
   - `logistics`:`ADD COLUMN disabled_by_overflow INTEGER NOT NULL DEFAULT 0`、`ADD COLUMN last_used_at INTEGER NOT NULL DEFAULT 0`、可选 `overflow_disabled_at INTEGER NULL`。
   - `users`:`ADD COLUMN trial_used INTEGER NOT NULL DEFAULT 0`、`ADD COLUMN trial_started_at INTEGER NOT NULL DEFAULT 0`、`ADD COLUMN trial_expires_at INTEGER NOT NULL DEFAULT 0`、`ADD COLUMN trial_plan_at_start TEXT NOT NULL DEFAULT ''`。
   - 新建表 `trial_overflow_window` + 唯一部分索引(`WHERE closed_at = 0`)。
2. **数据回填**:无需历史回填(新字段默认值即正确初始态)。
3. **schema 守卫**:更新 `scripts/check_schema_integrity.py`(若新增 CHECK 约束)。
4. **代码上线顺序**:
   - 先发后端(模型 + 迁移 + chokepoint + pricing 过滤 + 试用 API + scripts 脚本)。
   - 同时发部署变更(systemd timer + deploy.sh 安装步骤)。
   - 再发前端(横幅 / 模态 / 重选 / 灰色态)。
5. **回滚**:沿用 `deploy/rollback.sh <pre-deploy-tag>`;若已有用户领取试用,回滚后 `trial_used` 字段仍存在(因 alembic 不自动 downgrade 列),但功能不可用——回滚后需手动评估是否 `trial_used = 0` 恢复重试机会。
6. **冒烟**:部署后调用 `python -m scripts.trial_check --once --dry-run` 验证脚本可执行且不报错。

## Open Questions

- `trial_overflow_window` 表名是否最终采纳,或并入现有更通用表(实现阶段决定,不影响外部行为)。
- "速度优先 / 低价优先 / land / air"等 winner 集合的最终列表需要在实现阶段读 `pricing/calculate_pricing.py` 确认覆盖完整(规格已明确语义为"展示给用户的最终方案")。
- `trial_plan_at_start` 是否需要在试用结束时用于"还原回原套餐限额"——实际不需要,试用过期后真实 `subscription_type` 未变,limit 自然按真实套餐生效;字段保留作审计与统计。
