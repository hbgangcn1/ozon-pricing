## ADDED Requirements

### Requirement: Commission management gated by subscription tier
The system SHALL restrict commission category management (create/update/delete) to users with professional, enterprise, gratitude, or test subscription tiers. Free and efficiency tier users SHALL receive a 403 error with a message indicating upgrade is required.

#### Scenario: Free user tries to create commission category
- **WHEN** a user with user_type "free" attempts to create a commission category
- **THEN** the system returns HTTP 403 with message indicating this feature requires professional tier or above

#### Scenario: Professional user manages commissions
- **WHEN** a user with user_type "professional" creates a commission category
- **THEN** the operation succeeds

#### Scenario: Commission read access for all tiers
- **WHEN** a user with any subscription tier queries commission categories
- **THEN** the system returns their categories (read access is not gated)

### Requirement: Excel import/export gated by subscription tier
The system SHALL restrict Excel import and export functionality to users with enterprise, gratitude, or test subscription tiers. Free, efficiency, and professional tier users SHALL receive a 403 error.

#### Scenario: Professional user tries Excel export
- **WHEN** a user with user_type "professional" attempts to export data as Excel
- **THEN** the system returns HTTP 403 with message indicating this feature requires enterprise tier or above

#### Scenario: Enterprise user exports Excel
- **WHEN** a user with user_type "enterprise" uses Excel export
- **THEN** the operation succeeds

### Requirement: Frontend displays upgrade prompts for gated features
The system SHALL show visual indicators in the frontend UI when a feature is unavailable due to subscription tier. Gated features SHALL display a lock icon or upgrade prompt instead of the normal UI controls.

#### Scenario: Free user sees commission management locked
- **WHEN** a free tier user navigates to commission categories page
- **THEN** the page displays an upgrade prompt instead of the management interface

#### Scenario: Sidebar reflects feature availability
- **WHEN** the sidebar renders for a free/efficiency tier user
- **THEN** the commission categories menu item shows a lock indicator or is hidden based on tier
