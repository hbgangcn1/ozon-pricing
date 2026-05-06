## MODIFIED Requirements

### Requirement: Product batch import handles unrecognized file formats gracefully
The product batch import SHALL NOT crash when an unrecognized xlsx file is uploaded. Instead, it SHALL return a structured error message to the frontend.

#### Scenario: Importing unrecognized xlsx file shows error message
- **WHEN** user uploads `定价与物流表不计抛.xlsx` or any file the detector cannot recognize
- **THEN** the backend SHALL catch the ValueError from `detect_format`
- **AND** SHALL return HTTP 400 with a JSON body containing an error message and the sheet titles found
- **AND** the frontend SHALL display the error message instead of crashing

#### Scenario: Parser exception during preview returns structured error
- **WHEN** the backend parser throws an exception during file preview
- **THEN** the API SHALL catch the exception
- **AND** SHALL return HTTP 400 with `{"error": "<specific error message>"}`
- **AND** the frontend SHALL display the error message in the UI

#### Scenario: Frontend error boundary catches unexpected errors
- **WHEN** an uncaught error occurs during product import processing
- **THEN** the frontend error boundary SHALL display a user-friendly message
- **AND** SHALL provide a "重试" (Retry) button
