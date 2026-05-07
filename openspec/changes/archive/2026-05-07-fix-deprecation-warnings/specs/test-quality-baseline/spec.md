# Spec Delta: test-quality-baseline (fix-deprecation-warnings)

## ADDED Requirements

### Requirement: Test suite SHALL have zero deprecation warnings

The full test suite SHALL produce **0 DeprecationWarnings** under both `pytest -n0` and `pytest -n auto` execution modes.

This requirement supersedes the temporary "warnings ≤ baseline" exemption introduced by `fix-preexisting-test-failures` D4 修订. After this change ships, any new code that introduces a `DeprecationWarning` SHALL fail the strict CI gate.

#### Scenario: Production code uses non-deprecated datetime API

- **WHEN** any module under `services/`, `db/`, `api/`, `pricing/`, or top-level `*.py` reads or writes a UTC datetime
- **THEN** it SHALL use `datetime.now(datetime.UTC)` or `datetime.fromtimestamp(ts, datetime.UTC)`
- **AND** SHALL NOT use the deprecated `datetime.utcnow()` or `datetime.utcfromtimestamp()` APIs (Python 3.12+ deprecation)

#### Scenario: Test code uses non-deprecated datetime API

- **WHEN** any test under `tests/` constructs a UTC datetime
- **THEN** it SHALL use `datetime.now(datetime.UTC)`
- **AND** SHALL NOT use the deprecated `datetime.utcnow()` API

#### Scenario: Strict deprecation gate

- **WHEN** CI runs `pytest -n0 -W error::DeprecationWarning`
- **THEN** the run SHALL exit 0
- **AND** any new `DeprecationWarning` from project code SHALL cause the build to fail

#### Scenario: Third-party deprecation handling

- **WHEN** a deprecation warning originates from a third-party library (e.g. FastAPI's `HTTP_422_UNPROCESSABLE_ENTITY`)
- **THEN** the project SHALL either upgrade the library OR add a narrowly-scoped `warnings.filterwarnings` with a Priority 4 justification comment AND a tracking link to the upstream issue
- **AND** SHALL NOT mask warnings broadly via `filterwarnings("ignore")` without scope
