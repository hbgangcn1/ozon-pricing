## Purpose

pricing-empty-state capability spec.

## Requirements


### Requirement: Empty state prompt when no logistics rules exist
The PricingPage SHALL display a prominent empty state message when the user has no logistics rules configured. The message SHALL read "请先添加物流规则" and be visually prominent (not a subtle hint). The empty state SHALL appear in both fast mode and precise mode tabs. The page's calculation forms and buttons SHALL still be visible but the empty state provides clear guidance.

#### Scenario: User with no logistics rules opens PricingPage
- **WHEN** a user navigates to the PricingPage and has zero logistics rules in the system
- **THEN** the page displays a prominent banner or alert with text "请先添加物流规则" and an optional link/button to navigate to the logistics management page

#### Scenario: User with existing logistics rules opens PricingPage
- **WHEN** a user navigates to the PricingPage and has one or more logistics rules
- **THEN** the empty state banner is NOT displayed, and the page renders normally

#### Scenario: Empty state check uses existing API
- **WHEN** the PricingPage component mounts
- **THEN** it calls the existing logistics list API (`GET /api/logistics`) to determine if rules exist, without requiring any new backend endpoint

#### Scenario: Logistics API call fails during empty state check
- **WHEN** the logistics list API call fails
- **THEN** the empty state banner is NOT displayed (fail-open behavior — do not block the user)
