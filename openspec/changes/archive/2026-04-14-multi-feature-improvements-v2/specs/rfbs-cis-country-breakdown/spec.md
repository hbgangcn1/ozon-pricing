## ADDED Requirements

### Requirement: rFBS-CIS results broken down by country
The rFBS-独联体 calculation results SHALL be broken down into 6 individual countries: KZ (哈萨克斯坦), BY (白俄罗斯), KGZ (吉尔吉斯斯坦), UZ (乌兹别克斯坦), GE (格鲁吉亚), AZ (阿塞拜疆). Each country SHALL have its own calculation result.

#### Scenario: Backend calculates per-country results for rFBS-CIS
- **WHEN** `calculate_pricing_grouped` is called
- **THEN** instead of a single `rfbs_cis` key, it SHALL return `rfbs_KZ`, `rfbs_BY`, `rfbs_KGZ`, `rfbs_UZ`, `rfbs_GE`, `rfbs_AZ`
- **AND** each key SHALL contain the calculation result using only logistics rules matching that specific destination

#### Scenario: Frontend displays country sub-tabs for rFBS-CIS
- **WHEN** the pricing results page renders the rFBS-独联体 section
- **THEN** it SHALL display 6 sub-tabs or a dropdown for each CIS country
- **AND** selecting a country SHALL show only that country's calculation results

#### Scenario: Country with no matching logistics rules shows empty state
- **WHEN** a CIS country has no matching logistics rules
- **THEN** the sub-tab for that country SHALL display an empty state message like "该国家暂无可用物流方案"

#### Scenario: All CIS countries calculated independently
- **WHEN** the system calculates pricing for rfbs_KZ
- **THEN** it SHALL only use logistics rules where `destination == "KZ"` and `fulfillment_type == "rfbs"`
- **AND** the result SHALL be independent of other CIS country calculations
