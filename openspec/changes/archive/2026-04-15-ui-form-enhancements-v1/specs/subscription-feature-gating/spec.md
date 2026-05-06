## MODIFIED Requirements

### Requirement: SubscriptionPage reads plan data from API instead of mock
_(Modifies existing requirement "Frontend displays upgrade prompts for gated features")_

The SubscriptionPage SHALL replace its hardcoded `mockPlans` array with data fetched from `GET /api/subscriptions/plans`. This ensures that when admin modifies plans via PlanManagementPage, the changes are reflected in SubscriptionPage without code deployment.

#### Scenario: SubscriptionPage loads plans from API
- **WHEN** a user navigates to the SubscriptionPage
- **THEN** the page fetches plan data from `GET /api/subscriptions/plans` and renders the plan cards using the API response

#### Scenario: API returns empty or fails
- **WHEN** the `GET /api/subscriptions/plans` call returns an empty array or fails
- **THEN** the page displays an appropriate empty state or error message instead of falling back to mock data

#### Scenario: Plan data fields mapping
- **WHEN** the API response is received
- **THEN** the SubscriptionPage maps API fields (code, name, display_price_month, display_price_year, calc_limit, logistics_limit, features, status) to the UI card layout, maintaining the same visual structure as the current mock-based rendering
