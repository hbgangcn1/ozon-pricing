## MODIFIED Requirements

### Requirement: Merge priority results into grouped results
The pricing results page SHALL remove the standalone "价格优先方案" and "速度优先方案" sections. Their content SHALL be integrated into each group tab within the grouped calculation results.

#### Scenario: Grouped results contain priority recommendations
- **WHEN** calculation results are displayed
- **THEN** each group tab (rfbs_ru, rfbs_cis countries, fbp_ru, fbp_cis) SHALL display its own best land/air results
- **AND** there SHALL NOT be separate "价格优先方案" or "速度优先方案" sections outside the group tabs

### Requirement: Result card title format
Each result card within a group tab SHALL display its title in the format: `{物流名称} {Smart标志} {陆运/空运}`. The "自提" and "送货上门" delivery method distinction SHALL NOT appear in the title.

#### Scenario: Result card shows formatted title
- **WHEN** a result card is rendered for logistics rule named "OZON Express" with is_smart=1 and type="air"
- **THEN** the card title SHALL display "OZON Express Smart 空运"

#### Scenario: Result card for non-smart land logistics
- **WHEN** a result card is rendered for logistics rule named "中国邮政" with is_smart=0 and type="land"
- **THEN** the card title SHALL display "中国邮政 陆运" (no Smart badge)

#### Scenario: Self-pickup vs delivery distinction removed
- **WHEN** result cards are rendered
- **THEN** no card SHALL contain "自提" or "送货上门" labels in the title
