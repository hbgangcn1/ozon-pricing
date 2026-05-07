## MODIFIED Requirements

### Requirement: Plan CRUD API endpoints for admin management
The system SHALL provide REST API endpoints for admin users to create, read, update, delete, and toggle activation of subscription plans. All write endpoints SHALL require admin role authentication. The endpoints SHALL use the existing `db/plans.py` CRUD functions and reside in `api/routes/subscriptions.py` under the `/api/subscriptions/plans` prefix. The `features` field SHALL be serialized/deserialized using `|` (pipe) as the delimiter between the database string representation and the API `List[str]` representation.

#### Scenario: API returns features as separate array elements
- **WHEN** the database stores features as `"仅限快速模式|每日10次计算|1个物流模板|基础功能"`
- **THEN** the API response `features` field SHALL be `["仅限快速模式", "每日10次计算", "1个物流模板", "基础功能"]`

#### Scenario: Admin creates a plan with pipe-separated features
- **WHEN** an authenticated admin user sends `POST /api/subscriptions/plans` with `features: ["功能A", "功能B", "功能C"]`
- **THEN** the system SHALL store the features in the database as `"功能A|功能B|功能C"`

#### Scenario: Admin updates plan features
- **WHEN** an authenticated admin user sends `PUT /api/subscriptions/plans/{plan_id}` with `features: ["新功能1", "新功能2"]`
- **THEN** the system SHALL store the features in the database as `"新功能1|新功能2"`

### Requirement: PlanManagementPage connects to backend API
The PlanManagementPage SHALL replace all hardcoded `initialPlans` data with API calls. Page load SHALL fetch plans from `GET /api/subscriptions/plans`. Create, update, delete, and toggle operations SHALL call the corresponding API endpoints. The PlanEditForm features textarea SHALL use `|` (pipe) as the delimiter for splitting user input into an array and for joining an array back into display text. The textarea placeholder SHALL indicate that features are separated by `|`.

#### Scenario: Admin edits features in PlanEditForm
- **WHEN** admin enters `"功能A|功能B|功能C"` in the features textarea and saves
- **THEN** the form SHALL split by `|`, trim whitespace, filter empty strings, and send `features: ["功能A", "功能B", "功能C"]` to the API

#### Scenario: Features textarea displays existing features
- **WHEN** a plan with `features: ["功能A", "功能B"]` is loaded into the edit form
- **THEN** the textarea SHALL display `"功能A|功能B"`
