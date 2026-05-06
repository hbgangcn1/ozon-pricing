## MODIFIED Requirements

### Requirement: Logistics pool import uses append mode
The logistics pool import endpoint SHALL use INSERT (append) instead of UPSERT. Each import SHALL add new records without modifying or deleting existing ones.

#### Scenario: Importing a file appends new records
- **WHEN** admin uploads a logistics xlsx file to the import endpoint
- **THEN** all parsed rows SHALL be inserted as new records
- **AND** existing records with the same source_file/delivery_method/destination SHALL NOT be overwritten
- **AND** the response SHALL include the count of imported records

#### Scenario: Re-importing the same file creates duplicates
- **WHEN** admin imports the same file twice
- **THEN** the system SHALL create a second set of records
- **AND** the total count SHALL double

### Requirement: Import error messages include diagnostic details
When the xlsx format detection fails, the error response SHALL include the list of sheet titles found in the file, to help the user diagnose the format mismatch.

#### Scenario: Unrecognized xlsx format returns detailed error
- **WHEN** admin uploads an xlsx file that `detect_format` cannot match
- **THEN** the API SHALL return HTTP 400 with a message containing:
  - The fact that the format could not be recognized
  - The list of sheet titles found in the file
  - The list of supported format keywords

#### Scenario: Parser error during row processing returns row-level detail
- **WHEN** a row fails to parse during import
- **THEN** that row SHALL be skipped
- **AND** the error SHALL be recorded with the row index and error message
- **AND** the import SHALL continue processing remaining rows
