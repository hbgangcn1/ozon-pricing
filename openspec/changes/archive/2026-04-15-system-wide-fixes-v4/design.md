# Design: System Wide Fixes V4

## Context
The current system has several functional gaps and bugs across core modules:
- **Pricing Engine**: "Smart" logistics flags are lost between backend and frontend. Precision errors exist in profit margin calculations due to iterative rounding, and cost pie charts use an incorrect denominator.
- **Commission Management**: Data is currently global with no user isolation. All users see the same categories, and management is restricted to Admins, preventing individual user customization.
- **Subscription Gating**: Feature restrictions for different subscription tiers (Free, Efficiency, etc.) are not enforced in the backend or UI.
- **Statistics Module**: The module is largely non-functional, relying on hardcoded mock data in both frontend and backend. Many endpoints are unused or return logical errors.

## Goals / Non-Goals
### Goals
- Ensure "Smart" logistics labels reach the frontend UI.
- Correct pricing precision and pie chart visualization.
- Implement per-user isolation for commission categories with subscription-based access control.
- Replace mock statistics with real database queries and functional UI features (search, export, pagination).
- Clean up unused statistics endpoints.

### Non-Goals
- Implementation of a full multi-tenant architecture (beyond user isolation for specific models).
- Addition of real-time monitoring or websocket-based statistics.
- New features outside the scope of the identified bug fixes and module completions.

## Decisions

### 1. Smart Marking & Pricing Precision
- **Schema Update**: Add `is_smart` field to the `PricingResultItem` Pydantic schema.
- **Data Flow**: Update `format_result()` in `api/routes/pricing.py` to pass the `is_smart` boolean from the internal calculation engine to the API response.
- **Pie Chart**: Change the denominator in `CostPieChart.jsx` from `totalCost` to `totalPrice` (selling price) to accurately reflect cost percentages relative to revenue.
- **Formula Adjustment**: Refactor the profit margin calculation to use a deterministic denominator approach:
  `Price = Costs / (1 - target_margin - promotion - commission - withdrawal - payment - return - vat - agent_fee)`.
  This ensures that reverse-calculating the margin from the final price matches the user's target exactly.

### 2. Commission Category Isolation
- **Model Change**: Add `user_id` to the `CommissionCategory` model.
- **Constraint**: Implement a unique constraint on `(user_id, name)` to allow different users to have categories with the same name.
- **Logic**: Update `db/commission_categories.py` and `api/routes/commission_categories.py` to filter by `current_user_id`.
- **Pricing Integration**: The pricing engine will validate that the used commission category belongs to the requesting user.
- **FBP Calculation**: Automatically calculate FBP commission as `rFBS - 1%` to simplify management.

### 3. Subscription Feature Gating
- **Backend Middleware**: Implement a check in `api/dependencies.py` or within specific routes to verify the user's `user_type` against a feature matrix.
- **Frontend Gating**: Use conditional rendering and state-based disabling in the UI for:
  - Excel Import/Export: Restricted for Free/Efficiency/Professional tiers.
  - Commission Management: Restricted for Free/Efficiency tiers.

### 4. Statistics Module Overhaul
- **Database Queries**: Replace hardcoded responses with SQL aggregations for login logs, admin logs, and user activity.
- **Log Refinement**: Fix log data mapping (e.g., username instead of ID, meaningful action descriptions from user agents).
- **Interactive Features**: Implement backend support for search, CSV export, and pagination for all log tables.
- **Cleanup**: Remove 5 unused statistics endpoints (`funnel`, `user-groups`, `growth`, `feature-usage`, `plan-analysis`) and the "Exception Monitoring" tab.

## Risks / Trade-offs
- **Migration Impact**: Existing commission categories will be assigned to the Admin user, which may require manual adjustment if regular users previously expected to see them.
- **Calculation Drift**: Changing the pricing formula to improve margin precision might result in slightly different price outputs for existing saved products compared to their original calculations.
- **Performance**: Real-time aggregation for statistics (like retention) may become slow as the log table grows; indexing on timestamp and user_id fields will be critical.

## Migration Plan
- **Alembic Migration**: Generate a migration to add `user_id` to `commission_categories` and create the new unique constraint.
- **Data Migration Script**: A script to assign all existing null-user commission records to the primary Admin account.
- **Endpoint Deprecation**: Update the OpenAPI documentation to reflect the removal of defunct statistics endpoints.