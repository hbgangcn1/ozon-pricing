## ADDED Requirements

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
