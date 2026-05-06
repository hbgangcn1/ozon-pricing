## ADDED Requirements

### Requirement: Toggle logistics transport type
Each logistics rule in the logistics management page SHALL have a transport type toggle button. Land rules SHALL show "转为空运" button, air rules SHALL show "转为陆运" button.

#### Scenario: Clicking toggle on land rule switches to air
- **WHEN** user clicks "转为空运" on a land logistics rule
- **THEN** the system SHALL call `PATCH /api/logistics/{id}/toggle-transport`
- **AND** the rule's `type` field SHALL change from "land" to "air"
- **AND** the rule SHALL disappear from the 陆运 tab and appear in the 空运 tab
- **AND** a success toast SHALL confirm the change

#### Scenario: Clicking toggle on air rule switches to land
- **WHEN** user clicks "转为陆运" on an air logistics rule
- **THEN** the rule's `type` field SHALL change from "air" to "land"
- **AND** the rule SHALL move from 空运 tab to 陆运 tab

#### Scenario: Toggle transport API endpoint
- **WHEN** `PATCH /api/logistics/{id}/toggle-transport` is called
- **THEN** the backend SHALL flip the `type` field: "land" → "air" or "air" → "land"
- **AND** SHALL return the updated logistics record
- **AND** SHALL require authentication (current user must own the logistics rule)
