## MODIFIED Requirements

### Requirement: Price fields precision in logistics rule editor
The logistics rule editor SHALL limit `price_limit_cny` and `price_min_cny` input fields to exactly 2 decimal places. Both display and input MUST enforce this precision. The `step` attribute SHALL be set to `0.01`.

#### Scenario: Editing price limit with decimal precision
- **WHEN** user opens the logistics rule edit form
- **THEN** the `price_limit_cny` and `price_min_cny` fields SHALL display values rounded to 2 decimal places
- **AND** the input fields SHALL have `step="0.01"` attribute
- **AND** values with more than 2 decimal places SHALL be rounded on blur

#### Scenario: Saving price with excessive decimals
- **WHEN** user enters a value like `12.3456` in `price_limit_cny`
- **THEN** the system SHALL round it to `12.35` before saving

### Requirement: Hide battery capacity limit when allow_battery is checked
When the "允许电池" (`allow_battery`) checkbox is checked in the logistics rule editor, the "电池容量限制(Wh)" (`battery_wh_limit` / `battery_capacity_limit_wh`) input field SHALL be hidden. The field SHALL only be visible when `allow_battery` is unchecked or unset.

#### Scenario: Checking allow_battery hides capacity field
- **WHEN** user checks the "允许电池" checkbox
- **THEN** the "电池容量限制(Wh)" field SHALL be hidden from the form
- **AND** its value SHALL NOT be submitted with the form

#### Scenario: Unchecking allow_battery shows capacity field
- **WHEN** user unchecks the "允许电池" checkbox
- **THEN** the "电池容量限制(Wh)" field SHALL remain hidden (field is only relevant when battery is allowed but with limits)
