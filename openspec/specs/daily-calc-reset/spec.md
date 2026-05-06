## ADDED Requirements

### Requirement: Daily calculation count reset on login

The system SHALL reset a user's remaining calculation count to their plan's `calc_limit` value when the user logs in, if all of the following conditions are met:
- The user's plan has a finite `calc_limit` (not unlimited, i.e., `calc_limit != -1`)
- The user has not already been reset today (i.e., `last_calculations_reset_date` is not today's date)

The reset SHALL update:
- `remaining_calculations` to the plan's `calc_limit` value
- `last_calculations_reset_date` to today's date (ISO format `YYYY-MM-DD`)

#### Scenario: First login of the day for limited user

- **WHEN** a user with a limited plan (`calc_limit = 100`) logs in for the first time today
- **THEN** the system SHALL set `remaining_calculations` to `100`
- **AND** the system SHALL set `last_calculations_reset_date` to today's date

#### Scenario: Subsequent login same day for limited user

- **WHEN** a user with a limited plan logs in again on the same day after a previous reset
- **THEN** the system SHALL NOT modify `remaining_calculations`
- **AND** the system SHALL NOT modify `last_calculations_reset_date`

#### Scenario: Login for unlimited plan user

- **WHEN** a user with an unlimited plan (`calc_limit = -1`) logs in
- **THEN** the system SHALL NOT modify `remaining_calculations`
- **AND** the system SHALL NOT modify `last_calculations_reset_date`

#### Scenario: Login after date changes

- **WHEN** a user who was already reset yesterday logs in on a new day
- **THEN** the system SHALL reset `remaining_calculations` to the plan's `calc_limit`
- **AND** the system SHALL update `last_calculations_reset_date` to today's date

### Requirement: Frontend displays calculation limit as "per day"

The system SHALL display calculation limit text as "次/天" (times per day) instead of "次/月" (times per month) in all user-facing interfaces.

#### Scenario: Plan management page shows correct unit

- **WHEN** an admin views the plan list in PlanManagementPage
- **THEN** the calculation limit SHALL be displayed as `"{n}次/天"` where `n` is the `calc_limit` value

#### Scenario: Subscription page shows correct unit

- **WHEN** a user views their subscription status in SubscriptionPage
- **THEN** the calculation limit SHALL be displayed as `"{n}次/天"` where `n` is the remaining or plan limit

### Requirement: Reset function exported for use

The `reset_user_daily_calculations` function SHALL be exported from `db/__init__.py` to allow import by other modules.

#### Scenario: Function can be imported

- **WHEN** another module imports from `db.subscriptions`
- **THEN** `reset_user_daily_calculations` SHALL be available for import