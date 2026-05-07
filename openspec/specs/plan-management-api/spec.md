## Purpose

plan-management-api capability spec.
## Requirements
### Requirement: Plan CRUD API endpoints for admin management
The system SHALL provide REST API endpoints for admin users to create, read, update, delete, and toggle activation of subscription plans. All write endpoints SHALL require admin role authentication. The endpoints SHALL use the existing `db/plans.py` CRUD functions and reside in `api/routes/subscriptions.py` under the `/api/subscriptions/plans` prefix.

#### Scenario: Admin creates a new plan
- **WHEN** an authenticated admin user sends `POST /api/subscriptions/plans` with plan data (plan_code, plan_name, prices, limits, description, features, sort_order)
- **THEN** the system creates the plan in the database and returns the created plan with its generated id, HTTP 201

#### Scenario: Non-admin user tries to create a plan
- **WHEN** a non-admin user sends `POST /api/subscriptions/plans`
- **THEN** the system returns HTTP 403 with message "仅管理员可执行此操作"

#### Scenario: Admin updates an existing plan
- **WHEN** an authenticated admin user sends `PUT /api/subscriptions/plans/{plan_id}` with updated fields
- **THEN** the system updates only the provided fields and returns the updated plan data

#### Scenario: Admin updates a non-existent plan
- **WHEN** an authenticated admin user sends `PUT /api/subscriptions/plans/{plan_id}` with an id that does not exist
- **THEN** the system returns HTTP 404 with message "套餐不存在"

#### Scenario: Admin deletes a plan
- **WHEN** an authenticated admin user sends `DELETE /api/subscriptions/plans/{plan_id}`
- **THEN** the system removes the plan from the database and returns HTTP 200 with success confirmation

#### Scenario: Admin toggles plan active status
- **WHEN** an authenticated admin user sends `PATCH /api/subscriptions/plans/{plan_id}/toggle`
- **THEN** the system flips the plan's `is_active` value (1→0 or 0→1) and returns the new status

### Requirement: PlanManagementPage connects to backend API
The PlanManagementPage SHALL replace all hardcoded `initialPlans` data with API calls. Page load SHALL fetch plans from `GET /api/subscriptions/plans`. Create, update, delete, and toggle operations SHALL call the corresponding API endpoints. The page SHALL show loading states during API calls and error toasts on failure.

#### Scenario: Page loads with plans from API
- **WHEN** admin navigates to the PlanManagementPage
- **THEN** the page fetches plans from `GET /api/subscriptions/plans` and renders them in the table

#### Scenario: Page load fails
- **WHEN** the API call to fetch plans fails
- **THEN** the page shows an error toast and displays an empty state (not mock data)

#### Scenario: Admin creates a plan via the UI
- **WHEN** admin fills the plan creation form and clicks save
- **THEN** the page calls `POST /api/subscriptions/plans`, refreshes the plan list on success, and shows a success toast

#### Scenario: Admin deletes a plan via the UI
- **WHEN** admin clicks delete on a plan row and confirms the action
- **THEN** the page calls `DELETE /api/subscriptions/plans/{id}`, removes the row on success, and shows a success toast

### Requirement: Frontend API service methods for Plan CRUD
The `frontend/src/services/api.js` SHALL export plan management API methods: `getPlans()`, `createPlan(data)`, `updatePlan(id, data)`, `deletePlan(id)`, `togglePlanActive(id)`. These methods SHALL call the corresponding backend endpoints with JWT authentication headers.

#### Scenario: API service calls plan endpoints
- **WHEN** any plan management method is called
- **THEN** it sends the request to the correct endpoint with the auth token from the store

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

