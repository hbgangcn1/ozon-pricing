## MODIFIED Requirements

### Requirement: Commission management defaults to rFBS rates
The commission category editor SHALL use rFBS rates as the primary input. FBP rates SHALL be automatically computed as `rFBS rate - 1%` and displayed as read-only.

#### Scenario: Creating a new commission category with rFBS rates
- **WHEN** admin opens the commission category creation form
- **THEN** the form SHALL show input fields for rFBS Tier 1/2/3 rates
- **AND** FBP Tier 1/2/3 rates SHALL be displayed as read-only computed values (rFBS - 1%)
- **AND** a help text SHALL state "FBP 佣金根据 rFBS 佣金自动计算（rFBS - 1%）"

#### Scenario: Editing an existing commission category
- **WHEN** admin opens the edit form for an existing commission category
- **THEN** the rFBS Tier 1/2/3 rate fields SHALL be pre-filled with the stored rFBS values
- **AND** FBP rates SHALL be shown as computed read-only values

#### Scenario: Changing rFBS rate updates FBP display in real-time
- **WHEN** admin changes the rFBS Tier 1 rate from 10% to 12%
- **THEN** the FBP Tier 1 rate display SHALL immediately update to 11% (12% - 1%)

#### Scenario: API accepts rFBS rates and stores them
- **WHEN** the commission category create/update endpoint receives `rfbs_tier1_rate`, `rfbs_tier2_rate`, `rfbs_tier3_rate`
- **THEN** the system SHALL store the rFBS values in the database
- **AND** SHALL return both rFBS and computed FBP rates in the response

#### Scenario: Database migration preserves existing data
- **WHEN** Alembic migration adds rfbs_tier*_rate columns
- **THEN** existing fbp_tier*_rate values SHALL be used to compute rfbs values (rfbs = fbp + 1%)
- **AND** no existing data SHALL be lost
