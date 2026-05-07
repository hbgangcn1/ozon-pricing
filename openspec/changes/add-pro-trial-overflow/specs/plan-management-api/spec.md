## ADDED Requirements

### Requirement: 试用领取与状态查询端点

系统 SHALL 在 `api/routes/subscriptions.py` 中新增以下端点,均要求 JWT 认证:

- `POST /api/subscriptions/trial/claim`:领取 7 天专业版试用,语义见 `pro-trial` capability。
- `GET /api/subscriptions/trial/status`:查询当前用户试用状态。

两端点 SHALL 返回 JSON,字段命名与 `pro-trial` capability 中"试用状态查询接口"要求一致。

#### Scenario: 领取试用成功
- **WHEN** 符合资格的用户调用 `POST /api/subscriptions/trial/claim`
- **THEN** 系统返回 HTTP 200 与 `{ in_trial: true, trial_started_at: <epoch>, trial_expires_at: <epoch>, remaining_seconds: 604800 }`

#### Scenario: 重复领取被拒
- **WHEN** `trial_used = 1` 的用户调用 `POST /api/subscriptions/trial/claim`
- **THEN** 系统返回 HTTP 409 `{ error: "trial_already_used" }`

#### Scenario: 状态查询返回完整字段
- **WHEN** 任何认证用户调用 `GET /api/subscriptions/trial/status`
- **THEN** 系统返回 `{ eligible, in_trial, trial_used, trial_started_at, trial_expires_at, remaining_seconds }` 全部字段

### Requirement: 物流规则重选端点

系统 SHALL 在 `api/routes/logistics.py`(或 `api/routes/subscriptions.py`,实现阶段决定)新增 `POST /api/logistics/overflow/reselect` 端点,接受 `{ keep_ids: int[] }`。该端点 SHALL 仅在用户存在未关闭 `trial_overflow_window` 时可调用,且 `len(keep_ids) <= get_effective_logistics_limit(user)`。SHALL 在事务内将 `keep_ids` 中的规则置 `disabled_by_overflow = 0`,该用户其他启用规则置 `disabled_by_overflow = 1`,并将当前窗口标记为 `closed_at = now, close_reason = 'reselected'`(用户决策已完成,窗口关闭;后续如需再次裁剪需走新一轮升级/降级触发)。

#### Scenario: 用户在窗口内重选成功
- **WHEN** 用户在窗口未关闭时调用 `POST /api/logistics/overflow/reselect`,提交 N 个合法规则 ID(N <= effective limit)
- **THEN** 系统返回 HTTP 200 `{ kept_count: N, disabled_count: M }`,DB 状态按要求更新

#### Scenario: 窗口已关闭被拒
- **WHEN** 用户调用重选端点但当前不存在 `closed_at = 0` 的窗口
- **THEN** 系统返回 HTTP 409 `{ error: "no_active_window" }`

#### Scenario: 提交超额被拒
- **WHEN** 用户提交的 `keep_ids` 数量超过 `get_effective_logistics_limit(user)`
- **THEN** 系统返回 HTTP 400 `{ error: "exceeds_limit" }`

#### Scenario: 提交他人规则被拒
- **WHEN** 用户提交的 `keep_ids` 中包含不属于自己的规则 ID
- **THEN** 系统返回 HTTP 400 `{ error: "invalid_rule_ids" }`

### Requirement: 物流溢出窗口状态查询

系统 SHALL 提供 `GET /api/logistics/overflow/status` 端点,返回当前用户是否存在未关闭窗口、窗口剩余秒数、当前被 `disabled_by_overflow = 1` 的规则数量,供前端模态弹出与列表灰色态展示决策。

#### Scenario: 存在未关闭窗口
- **WHEN** 用户存在 `closed_at = 0 AND expires_at > now` 的窗口
- **THEN** 系统返回 `{ has_open_window: true, window_expires_at: <epoch>, remaining_seconds: <int>, overflow_disabled_count: <int> }`

#### Scenario: 无未关闭窗口但仍有溢出禁用规则
- **WHEN** 用户没有未关闭窗口但仍有 `disabled_by_overflow = 1` 规则(窗口已自然过期)
- **THEN** 系统返回 `{ has_open_window: false, overflow_disabled_count: <int> }`,前端可据此持续显示灰色态但不弹模态
