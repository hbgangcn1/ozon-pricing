## ADDED Requirements

### Requirement: View logistics pool item details
Each logistics pool record in the list SHALL have a "查看" (View) button. Clicking it SHALL open a read-only dialog displaying all fields of that logistics rule.

#### Scenario: Clicking view button opens detail dialog
- **WHEN** user clicks the "查看" button on a logistics pool record
- **THEN** a dialog SHALL open displaying all fields of that record in read-only mode
- **AND** no edit controls SHALL be present in the dialog

#### Scenario: Detail dialog displays all logistics fields
- **WHEN** the detail dialog is open
- **THEN** it SHALL display: name, type, delivery_method, fulfillment_type, destination, min/max_days, price limits, weight limits, dimension limits, fee configuration, battery/liquid permissions, volume mode, priority group, is_smart, fbp_service_level, fbp_company, source_file
- **AND** all values SHALL be formatted for readability (e.g., boolean fields show "是/否")

#### Scenario: Closing detail dialog
- **WHEN** user clicks the close button or clicks outside the dialog
- **THEN** the dialog SHALL close without any side effects
