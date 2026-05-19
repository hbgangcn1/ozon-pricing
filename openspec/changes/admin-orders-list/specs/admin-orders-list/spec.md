## ADDED Requirements

### Requirement: Admin can view all user orders
The system SHALL provide an API endpoint that returns all users' payment orders with pagination, accessible only to admin users.

#### Scenario: Admin fetches all orders
- **WHEN** admin sends GET /api/statistics/orders with page=1&page_size=20
- **THEN** system returns a paginated list of all orders with fields: order_id, username, amount, order_type, status, created_at

#### Scenario: Non-admin is rejected
- **WHEN** a non-admin user sends GET /api/statistics/orders
- **THEN** system returns HTTP 403

### Requirement: Search orders by username or order_id
The system SHALL support fuzzy search across username and order_id fields.

#### Scenario: Search by username
- **WHEN** admin sends GET /api/statistics/orders?search=robert
- **THEN** system returns orders where the associated username contains "robert" (case-insensitive)

#### Scenario: Search by order_id
- **WHEN** admin sends GET /api/statistics/orders?search=ORD_abc
- **THEN** system returns orders where order_id contains "ORD_abc"

#### Scenario: Empty search returns all
- **WHEN** admin sends GET /api/statistics/orders?search=
- **THEN** system returns all orders (no search filter applied)

### Requirement: Filter orders by status
The system SHALL support filtering orders by payment status via a query parameter.

#### Scenario: Filter by SUCCESS
- **WHEN** admin sends GET /api/statistics/orders?status=SUCCESS
- **THEN** system returns only orders with status=SUCCESS

#### Scenario: No status filter returns all
- **WHEN** admin sends GET /api/statistics/orders without status parameter
- **THEN** system returns orders of all statuses

### Requirement: Filter orders by date range
The system SHALL support filtering orders by created_at date range.

#### Scenario: Date range filter
- **WHEN** admin sends GET /api/statistics/orders?date_from=2026-01-01&date_to=2026-01-31
- **THEN** system returns orders created between 2026-01-01 00:00:00 and 2026-01-31 23:59:59

#### Scenario: Only date_from
- **WHEN** admin sends GET /api/statistics/orders?date_from=2026-01-01
- **THEN** system returns orders created on or after 2026-01-01

### Requirement: Frontend orders tab
The StatisticsPage SHALL display an "订单记录" tab that shows a table of all user orders with search, status filter, date range filter, and pagination.

#### Scenario: Tab displays order table
- **WHEN** admin navigates to Statistics page and clicks "订单记录" tab
- **THEN** system displays a table with columns: 订单号, 用户名, 金额, 套餐类型, 状态, 创建时间

#### Scenario: Search input filters results
- **WHEN** admin types in the search box
- **THEN** table results are filtered by username or order_id matching the input (debounced 300ms)

#### Scenario: Status dropdown filters results
- **WHEN** admin selects "SUCCESS" from the status dropdown
- **THEN** table shows only SUCCESS orders

#### Scenario: Pagination works
- **WHEN** admin clicks "下一页"
- **THEN** table shows the next page of results
