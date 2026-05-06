## MODIFIED Requirements

### Requirement: Remove battery capacity details from product editor
The product editor in both precision mode and the product list edit popup SHALL remove the following fields:
- "电池容量填写方式" radio group (`battery_capacity_type`)
- "容量(Wh)" input field
- "容量(mAh)" input field
- "电压(V)" input field
- "有 MSDS 证书" checkbox

Only the "含电池" (`has_battery`) checkbox SHALL remain as a simple boolean toggle.

#### Scenario: Precision mode product form renders without battery detail fields
- **WHEN** user opens the precision mode product editing area in PricingPage
- **THEN** the form SHALL show the "含电池" checkbox
- **AND** the form SHALL NOT show battery_capacity_type radio, Wh input, mAh input, V input, or MSDS checkbox

#### Scenario: Product edit popup renders without battery detail fields
- **WHEN** user clicks edit on a product in the product list and the edit popup opens
- **THEN** the popup SHALL show the "含电池" checkbox
- **AND** the popup SHALL NOT show battery_capacity_type radio, Wh input, mAh input, V input, or MSDS checkbox

#### Scenario: Saving product with has_battery only
- **WHEN** user checks "含电池" and saves the product
- **THEN** the product SHALL be saved with `has_battery=true`
- **AND** battery_capacity_type, battery_wh, battery_mah, battery_v, has_msds fields SHALL NOT be sent in the request
