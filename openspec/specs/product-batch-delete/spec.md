## Purpose

product-batch-delete capability spec.

## Requirements


### Requirement: Batch selection in product list dialog
The product list dialog in PricingPage precise mode SHALL include a Checkbox for each product row enabling single selection, and a "select all" Checkbox in the header area. Selection state SHALL be independent of product editing or form population.

#### Scenario: User selects individual products
- **WHEN** the user opens the product list dialog and clicks the Checkbox next to a product
- **THEN** that product is marked as selected, indicated by a checked Checkbox

#### Scenario: User selects all products
- **WHEN** the user clicks the "全选" Checkbox in the dialog header
- **THEN** all products in the list are selected

#### Scenario: User deselects all
- **WHEN** all products are selected and the user unchecks the "全选" Checkbox
- **THEN** all products are deselected

#### Scenario: Partial selection shows indeterminate state
- **WHEN** some but not all products are selected
- **THEN** the "全选" Checkbox shows an indeterminate state

### Requirement: Batch delete with confirmation
When one or more products are selected in the product list dialog, a delete button SHALL appear. Clicking the delete button SHALL trigger a confirmation dialog before executing the deletion.

#### Scenario: Delete button visibility
- **WHEN** zero products are selected
- **THEN** the batch delete button is NOT visible or is disabled

#### Scenario: Delete button shows count
- **WHEN** N products are selected (N ≥ 1)
- **THEN** the batch delete button is visible and shows the count, e.g. "删除选中 (N)"

#### Scenario: User confirms batch deletion
- **WHEN** the user clicks the batch delete button and confirms in the AlertDialog
- **THEN** the system calls `DELETE /api/products/{id}` for each selected product (using Promise.allSettled), refreshes the product list, clears selection, and shows a success toast with count

#### Scenario: User cancels batch deletion
- **WHEN** the user clicks the batch delete button but cancels in the AlertDialog
- **THEN** no products are deleted and selection is preserved

#### Scenario: Partial failure during batch deletion
- **WHEN** some DELETE requests succeed and some fail
- **THEN** the system shows a toast indicating how many succeeded and how many failed, and refreshes the product list to reflect the current state
