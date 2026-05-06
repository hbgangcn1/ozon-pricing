## ADDED Requirements

### Requirement: Delete all logistics pool records
The system SHALL provide a "删除全部" (Delete All) button on the logistics pool management page. This operation SHALL physically delete all records from the logistics_pool table.

#### Scenario: Admin clicks delete all with confirmation
- **WHEN** admin clicks the "删除全部" button
- **THEN** a confirmation dialog SHALL appear with a warning message
- **AND WHEN** admin confirms the deletion
- **THEN** all records in the logistics_pool table SHALL be physically deleted
- **AND** the UI SHALL refresh to show an empty list
- **AND** a success toast SHALL be displayed

#### Scenario: Admin cancels delete all
- **WHEN** admin clicks the "删除全部" button
- **AND** admin clicks "取消" on the confirmation dialog
- **THEN** no records SHALL be deleted
- **AND** the dialog SHALL close

#### Scenario: Non-admin cannot see delete all button
- **WHEN** a non-admin user views the logistics pool page
- **THEN** the "删除全部" button SHALL NOT be rendered

#### Scenario: Delete all endpoint requires admin role
- **WHEN** a non-admin user calls `DELETE /api/logistics-pool/all`
- **THEN** the API SHALL return HTTP 403
