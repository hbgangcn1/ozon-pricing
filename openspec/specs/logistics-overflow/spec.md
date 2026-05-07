# logistics-overflow Specification

## Purpose
TBD - created by archiving change add-pro-trial-overflow. Update Purpose after archive.
## Requirements
### Requirement: 物流规则溢出禁用列

`logistics` 表 SHALL 新增 `disabled_by_overflow INTEGER NOT NULL DEFAULT 0` 列,与现有 `is_active` 并列存在。所有 pricing 路径与"启用规则数"统计 SHALL 同时过滤 `is_active == 1 AND disabled_by_overflow == 0`。`is_active` 语义保持不变(仅由用户手动启用/禁用驱动)。

#### Scenario: pricing 跳过被溢出禁用的规则
- **WHEN** 某规则 `is_active = 1` 且 `disabled_by_overflow = 1`
- **THEN** 该规则不参与定价计算的任何阶段,亦不出现在最终展示结果中

#### Scenario: 用户手动禁用与溢出禁用互不干扰
- **WHEN** 某规则 `is_active = 0` 且 `disabled_by_overflow = 1`
- **THEN** 升级恢复仅置 `disabled_by_overflow = 0`,`is_active` 保持 `0`

### Requirement: 物流规则 last_used_at 列与 MRU 更新

`logistics` 表 SHALL 新增 `last_used_at INTEGER NOT NULL DEFAULT 0` 列(epoch seconds)。系统 SHALL 在每次 `/api/pricing/calculate` 等定价接口产出最终响应后,从最终展示给用户的所有 winner 中收集规则 ID,通过单条批量 UPDATE 写入 `last_used_at = now`,且应用节流条件 `last_used_at < now - 60`。`pricing/` 模块下的纯计算函数(包括 `select_best.py`)SHALL NOT 直接写库。

#### Scenario: 最终入选规则被批量更新一次
- **WHEN** 一次定价请求产出 K 个最终 winner(去重后)
- **THEN** 系统执行单条 `UPDATE logistics SET last_used_at = :now WHERE user_id = :uid AND id IN (...) AND last_used_at < :now - 60`,影响行数 ≤ K

#### Scenario: SSE progress 事件不写库
- **WHEN** 定价过程产生若干 SSE progress 事件
- **THEN** 不触发任何对 `last_used_at` 的写入

#### Scenario: 候选集与淘汰规则不算 used
- **WHEN** 某规则进入 cost_filter 候选集但未在最终响应胜出
- **THEN** 该规则的 `last_used_at` 不被更新

#### Scenario: 手动编辑不算 used
- **WHEN** 用户通过 PUT/PATCH 修改某规则
- **THEN** 该规则的 `last_used_at` 不被更新(语义为"使用",非"编辑")

### Requirement: 试用结束 / 降级时自动裁剪

当用户的"启用且未被溢出禁用的规则数"超过有效套餐限额(`get_effective_logistics_limit(user)` 返回正值)时,系统 SHALL 在 T+0 自动裁剪保留 N 条最近使用的规则,其余规则置 `disabled_by_overflow = 1`。裁剪触发场景包括:试用过期(由 `trial_check` 脚本处理)与降级(由 `apply_subscription_change` 处理)。

#### Scenario: 试用过期触发自动裁剪
- **WHEN** `trial_check` 处理一个免费用户,`trial_expires_at < now` 且当前启用规则数 = 7
- **THEN** 系统按 `ORDER BY last_used_at DESC, id DESC` 保留 1 条,其余 6 条置 `disabled_by_overflow = 1`,并开启一个新的 48h 重新选择窗口

#### Scenario: 降级触发自动裁剪
- **WHEN** `apply_subscription_change` 将用户从 `professional` 降级至 `efficiency`,当前启用规则数 = 5
- **THEN** 系统在同一事务内保留 3 条最近使用规则,其余 2 条置 `disabled_by_overflow = 1`,并开启 48h 窗口

#### Scenario: 限额为无限不触发裁剪
- **WHEN** 用户有效套餐限额为 `-1`
- **THEN** 不执行任何裁剪,且不开启窗口

#### Scenario: 当前规则数已不超限不触发裁剪
- **WHEN** 试用过期但用户启用规则数 ≤ 真实套餐限额
- **THEN** 不裁剪、不开窗

### Requirement: 48 小时重新选择窗口

每次裁剪 SHALL 同时插入一条 `trial_overflow_window` 记录(`opened_at = now`、`expires_at = now + 48 * 3600`、`closed_at = 0`)。同一用户同一时刻只能存在一条 `closed_at = 0` 的记录(由部分唯一索引保证)。窗口期内,用户 SHALL 可通过接口将自己启用规则集合中的任意 N 条置为"保留",其余被自动溢出禁用。窗口过期时由 `trial_check` 关闭(`close_reason = 'expired'`),不再二次裁剪。

#### Scenario: 用户在窗口内重新选择保留集
- **WHEN** 用户在窗口未关闭时调用重新选择接口,提交 N 个规则 ID(N ≤ 有效限额)
- **THEN** 系统在事务内将所选 N 个规则的 `disabled_by_overflow = 0`,其余被该用户启用的规则 `disabled_by_overflow = 1`,并将当前窗口标记为 `closed_at = now, close_reason = 'reselected'`(用户决策已完成,窗口关闭)

#### Scenario: 提交保留数超过限额被拒绝
- **WHEN** 用户提交的保留 ID 数量超过 `get_effective_logistics_limit(user)`
- **THEN** 系统返回 HTTP 400 `{ error: "exceeds_limit" }`,不修改任何字段

#### Scenario: 窗口过期由后台关闭
- **WHEN** `trial_check` 检测到 `closed_at = 0 AND expires_at < now`
- **THEN** 系统将该窗口 `closed_at = now, close_reason = 'expired'`,不修改任何 logistics 行

#### Scenario: 同一用户不开重复窗口
- **WHEN** 已存在 `closed_at = 0` 窗口的用户再次触发裁剪条件
- **THEN** 系统不开新窗口、不重复裁剪

### Requirement: 升级到 professional / enterprise 恢复溢出禁用

`db/subscriptions.apply_subscription_change(...)` 在新套餐为 `professional` 或 `enterprise` 时 SHALL 在同一事务内执行恢复操作:`UPDATE logistics SET disabled_by_overflow = 0 WHERE user_id = :uid AND disabled_by_overflow = 1`,并将该用户所有 `closed_at = 0` 的窗口标记为 `closed_at = now, close_reason = 'upgraded'`。该操作 SHALL 是幂等的。

#### Scenario: 升级一次性恢复全部溢出禁用规则
- **WHEN** 一个有 6 条 `disabled_by_overflow = 1` 规则的用户升级到 `professional`
- **THEN** 6 条规则的 `disabled_by_overflow` 全部归零,该用户所有未关闭窗口被标记为 `upgraded`

#### Scenario: 升级不影响用户手动禁用的规则
- **WHEN** 用户有 3 条规则:A(`is_active=0, disabled_by_overflow=1`)、B(`is_active=1, disabled_by_overflow=1`)、C(`is_active=1, disabled_by_overflow=0`),升级到 `enterprise`
- **THEN** 升级后 A 仍 `is_active=0, disabled_by_overflow=0`(用户手动禁用保留),B 变 `is_active=1, disabled_by_overflow=0`,C 不变

#### Scenario: 重复升级回调幂等
- **WHEN** 同一升级事件回调被微信重发两次,均经由 `apply_subscription_change`
- **THEN** 第二次调用不重复改动状态,函数返回成功

### Requirement: 前端溢出与重新选择 UI

前端物流规则页面 SHALL 对 `disabled_by_overflow = 1` 的规则以灰色态展示并标注"已被套餐限额禁用",且对存在未关闭窗口的用户提供"重新选择保留规则"入口与模态。模态 SHALL 在用户进入物流规则页面时自动弹出一次,后续仅在用户主动点击入口时再次打开。

#### Scenario: 灰色态展示溢出禁用规则
- **WHEN** 用户访问物流规则页面,某规则 `disabled_by_overflow = 1`
- **THEN** 该行以灰色态渲染并显示"已被套餐限额禁用",不可参与定价

#### Scenario: 进入页面自动弹出重选模态
- **WHEN** 用户首次在窗口未关闭期间进入物流规则页面
- **THEN** 系统弹出重新选择模态,展示当前启用规则与保留 N 条的限额

#### Scenario: 提交重选成功后关闭模态
- **WHEN** 用户在模态中提交合法保留集合并成功
- **THEN** 模态关闭,列表刷新,被保留的规则正常态显示,其余继续灰色态

