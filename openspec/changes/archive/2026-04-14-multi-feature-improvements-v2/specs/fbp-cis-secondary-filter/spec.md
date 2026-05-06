## ADDED Requirements

### Requirement: FBP results secondary filtering by company and service level
For FBP-俄 and FBP-CIS calculation results, the system SHALL apply a secondary filtering step: group candidates by (fbp_company, fbp_service_level), take the highest-price candidate from each group, then select the overall best from those candidates using the user's priority preference (低价优先 or 速度优先).

#### Scenario: FBP secondary filter groups by company and service level
- **WHEN** FBP calculation produces candidates from multiple companies and service levels
- **THEN** the system SHALL group candidates by `(fbp_company, fbp_service_level)`
- **AND** within each group, SHALL select the candidate with the highest logistics cost
- **AND** SHALL apply the user's priority preference (价格/速度) to select the final best from those group representatives

#### Scenario: FBP secondary filter with single company
- **WHEN** all FBP candidates belong to the same company and service level
- **THEN** the secondary filter SHALL select the highest-cost candidate from that single group
- **AND** that candidate SHALL be the final result

#### Scenario: FBP secondary filter preserves debug information
- **WHEN** the secondary filter processes candidates
- **THEN** the result SHALL include information about which groups were formed
- **AND** which candidate was selected from each group
- **AND** the final selection rationale
