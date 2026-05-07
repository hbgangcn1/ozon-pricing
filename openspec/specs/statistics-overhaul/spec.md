## Purpose

statistics-overhaul capability spec.

## Requirements


### Requirement: Overview tab displays real data from API
The system SHALL replace all hardcoded mock data in the overview tab with real data fetched from `/api/statistics/overview`. Active users SHALL be calculated based on users with `last_login` within the last 30 days, not set equal to total users.

#### Scenario: Overview loads real statistics
- **WHEN** admin navigates to the statistics overview tab
- **THEN** total users, active users (30-day login), today's new users, total revenue, and subscription tier counts are fetched from the API and displayed with real values

#### Scenario: Active users reflects real activity
- **WHEN** there are 100 total users but only 40 have logged in within 30 days
- **THEN** the overview shows total_users=100 and active_users=40

### Requirement: Retention analysis uses real login data
The system SHALL calculate monthly retention rates based on `user_login_logs`. Retention for month N means: of users who registered in month M, what percentage had at least one login in month M+N.

#### Scenario: Monthly retention calculation
- **WHEN** 10 users registered in January and 8 of them logged in during February
- **THEN** the 1-month retention rate for the January cohort is 80%

#### Scenario: No login data available
- **WHEN** there are no login logs for a given period
- **THEN** the system displays "暂无数据" instead of fake numbers

### Requirement: User activity tab shows real daily/weekly active users with real trends
The system SHALL display real DAU (daily active users) and WAU (weekly active users) based on `last_login`. Trend values SHALL be calculated as the difference vs the previous period (today vs yesterday, this week vs last week).

#### Scenario: Real trend calculation
- **WHEN** today's active users are 38 and yesterday's were 35
- **THEN** the daily trend displays "+3" (not hardcoded "+5")

### Requirement: Revenue tab shows real payment data
The system SHALL query `payment_orders` table grouped by month to display real monthly revenue. The overview cards SHALL show real current month revenue, cumulative revenue, and paid user count.

#### Scenario: Monthly revenue breakdown
- **WHEN** admin views the revenue tab
- **THEN** revenue is displayed per month based on actual payment_orders with status='SUCCESS', grouped by month

### Requirement: Login logs display correct field mappings
The system SHALL display real usernames (not numeric IDs), actual login action types (not user_agent strings), and real login status (success/failure based on actual result, not hardcoded "success").

#### Scenario: Login log shows real username
- **WHEN** user with ID 5 and username "张三" has a login log entry
- **THEN** the log displays username "张三", not "5"

#### Scenario: Failed login shows failure status
- **WHEN** a login attempt fails (wrong password)
- **THEN** the login log entry shows status "失败" (not hardcoded "成功")

### Requirement: Admin logs display real admin username
The system SHALL display the admin's username (not numeric admin_id) in admin action logs.

#### Scenario: Admin log shows username
- **WHEN** admin user with ID 1 and username "admin" performs an action
- **THEN** the log displays admin "admin", not "1"

### Requirement: Log tabs support search, export, and pagination
The system SHALL implement functional search (filter by username/action), CSV export, and server-side pagination for both login logs and admin logs tabs. Pagination SHALL use real page/page_size query parameters.

#### Scenario: Search filters login logs
- **WHEN** admin types "张三" in the search box on login logs tab
- **THEN** only login log entries for user "张三" are displayed

#### Scenario: Export downloads CSV
- **WHEN** admin clicks the export button on admin logs tab
- **THEN** a CSV file containing the current log data is downloaded

#### Scenario: Pagination navigates pages
- **WHEN** there are 50 login log entries and page_size is 20
- **THEN** the pagination shows 3 pages and navigating to page 2 loads entries 21-40

### Requirement: Exception monitoring tab is removed
The system SHALL remove the "异常监控" tab from the statistics page entirely.

#### Scenario: Statistics page has 6 tabs
- **WHEN** admin navigates to the statistics page
- **THEN** there are exactly 6 tabs: 总览, 留存分析, 用户活跃, 充值与收入, 操作日志, 登录记录

### Requirement: Unused backend endpoints are deleted
The system SHALL remove the following 5 statistics API endpoints: `/funnel`, `/user-groups`, `/growth`, `/feature-usage`, `/plan-analysis`. Related database functions and schema models SHALL also be removed.

#### Scenario: Deleted endpoint returns 404
- **WHEN** a client sends GET to `/api/statistics/funnel`
- **THEN** the server returns HTTP 404 (endpoint no longer exists)
