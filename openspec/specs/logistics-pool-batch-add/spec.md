# logistics-pool-batch-add Specification

## Purpose
TBD - created by archiving change fix-logistics-pool-batch-add-savepoint. Update Purpose after archive.
## Requirements
### Requirement: Batch add public pool entries to user logistics

The system SHALL provide `POST /api/logistics-pool/batch-add-to-my-logistics` accepting a JSON body `{"ids": [int, ...]}` and SHALL copy each referenced public pool entry into the authenticated user's logistics table, returning a JSON object `{added: int, not_found: list[int], new_ids: list[int], errors: list[str]}` with HTTP 200.

The endpoint MUST require authentication via the project's standard JWT/cookie dependency. The endpoint MUST enforce the user's subscription logistics quota (`_check_logistics_limit`) BEFORE attempting any insert; if quota would be exceeded the endpoint MUST return the existing quota error (per `_check_logistics_limit` contract) without partial inserts.

The endpoint MUST validate `ids` length: empty list returns HTTP 400 with detail `"ids 不能为空"`; more than 200 ids returns HTTP 400 with detail `"单次最多添加 200 条"`. (NOTE: 400 is the existing behavior preserved for backward compatibility; this is intentionally NOT 422.)

#### Scenario: Successful full batch
- **WHEN** authenticated user POSTs `{"ids": [p1, p2, p3]}` where all three pool ids exist and quota allows three inserts
- **THEN** response is HTTP 200 with `added=3`, `not_found=[]`, `new_ids` containing 3 new logistics ids, `errors=[]`
- **AND** three new rows exist in the logistics table owned by the user

#### Scenario: Partial not_found
- **WHEN** authenticated user POSTs `{"ids": [p1, 999999]}` where `p1` exists and `999999` does not
- **THEN** response is HTTP 200 with `added=1`, `not_found=[999999]`, `new_ids` containing 1 id, `errors=[]`

#### Scenario: Empty ids rejected with 400
- **WHEN** authenticated user POSTs `{"ids": []}`
- **THEN** response is HTTP 400 with `detail="ids 不能为空"`

#### Scenario: Over-limit ids rejected with 400
- **WHEN** authenticated user POSTs `{"ids": [...201 ids...]}`
- **THEN** response is HTTP 400 with `detail="单次最多添加 200 条"`

#### Scenario: Quota exceeded blocks all inserts
- **WHEN** user's subscription allows N more logistics rows and request contains N+1 ids
- **THEN** response is the existing quota error (per `_check_logistics_limit` contract) and zero rows are inserted

### Requirement: Per-row failure isolation in batch add (database errors only)

The batch endpoint MUST wrap each pool-id's insert in a SQLAlchemy SAVEPOINT (`async with session.begin_nested():`). If a single insert raises a SQLAlchemy database-level exception (`IntegrityError`, `DataError`, `StatementError`, or non-fatal `DBAPIError`), the SAVEPOINT MUST roll back, the loop MUST continue with subsequent ids, and a human-readable error string identifying the failed pool id MUST be appended to the response `errors` list. Database-level single-row failures MUST NOT cause HTTP 500 nor abort the remaining batch.

The endpoint MUST NOT catch `Exception` indiscriminately. Programmer errors (`AttributeError`, `TypeError`, `KeyError`, `InvalidRequestError`) and non-database system errors MUST propagate to the global handler so real bugs surface as HTTP 500 with traceback rather than being hidden as "row failures" in `errors[]`.

`DBAPIError` instances where `connection_invalidated == True` MUST be re-raised (not captured into `errors`), because the entire session is unusable and continuing the loop is meaningless.

`KeyboardInterrupt`, `SystemExit`, and other `BaseException` subclasses MUST NOT be caught — they propagate normally.

The endpoint MUST log every caught exception with full structured context via `logger.warning(...)` for postmortem (level chosen because per-row data errors are expected operational events, not bugs).

#### Scenario: Single IntegrityError does not poison the batch
- **WHEN** request contains `[good_id_1, bad_id, good_id_2]` where `bad_id`'s insert violates a CHECK constraint (e.g. invalid `volume_mode`)
- **THEN** response is HTTP 200 with `added=2`, `new_ids` containing 2 ids, `errors` containing 1 string mentioning the failed row
- **AND** the two good rows ARE persisted (visible in subsequent queries)
- **AND** `recalculate_priority_groups` is called once at end without raising

#### Scenario: SQLAlchemy DataError isolated like IntegrityError
- **WHEN** an insert raises `sqlalchemy.exc.DataError` (e.g. enum value out of range, string too long for column)
- **THEN** response is still HTTP 200, the bad id appears in `errors`, and remaining ids are processed

#### Scenario: Programmer error escapes to 500
- **WHEN** an insert raises a non-database exception such as `AttributeError` (indicating a code bug, not a data problem)
- **THEN** the exception propagates to the global exception handler and the endpoint returns HTTP 500
- **AND** the failure is NOT silently captured into `errors[]`
- **AND** the full traceback is logged via the global handler

#### Scenario: SAVEPOINT rollback preserves session usability
- **WHEN** any single insert fails inside its SAVEPOINT
- **THEN** the outer session remains usable for subsequent SAVEPOINTs and the final `recalculate_priority_groups` call
- **AND** no `PendingRollbackError` is raised

### Requirement: Single-entry add uses SAVEPOINT for consistency

`POST /api/logistics-pool/{pool_id}/add-to-my-logistics` MUST wrap its `create_logistics` call in `async with session.begin_nested():` so that any database-level failure leaves the outer session in a clean state for the request-scoped commit/rollback in `get_db()`.

The single-entry route MUST NOT catch exceptions added by this change. Existing exception semantics (HTTP 4xx/5xx mapping) remain unchanged. The SAVEPOINT only ensures session hygiene; it does not alter response shape or status codes.

External response shape MUST remain unchanged: `{"id": int}` on success, existing error semantics on failure.

#### Scenario: Successful single add (regression guard)
- **WHEN** authenticated user POSTs to `/api/logistics-pool/{existing_pool_id}/add-to-my-logistics`
- **THEN** response is HTTP 200 with `{"id": <new_logistics_id>}` and the row exists in logistics

#### Scenario: Single add IntegrityError surfaces cleanly
- **WHEN** the insert raises `IntegrityError` (e.g. forced CHECK violation)
- **THEN** the SAVEPOINT rolls back, the outer session remains usable, and the endpoint returns HTTP 500 (existing behavior) without leaving a `PendingRollbackError` for the next request that reuses the connection

### Requirement: Stdlib logging traceback reaches loguru file sink

The application MUST ensure that when stdlib `logging` is used with `exc_info=True` (e.g. `api/main.py:274` global exception handler), the resulting traceback IS written to the loguru file sink at `logs/logistics_error_<date>.log` and is non-empty after the failed request completes.

The bridge from stdlib logging to loguru already exists (`logger_config.InterceptHandler` registered via `logging.basicConfig(force=True)` at module import). The remaining gap is that the loguru `format_log` function in `logger_config.py` does not include the `{exception}` template variable, causing tracebacks to be silently dropped from formatted output. This MUST be fixed so the format string emits the traceback after the message.

The fix MUST preserve original log level, exception traceback (`exc_info`), logger name, and source file/line metadata.

The fix MUST NOT cause double-logging of records that loguru itself emits (loguru records do not pass through `InterceptHandler`).

#### Scenario: Global exception handler traceback reaches loguru file sink
- **WHEN** a route raises an unhandled exception and `api/main.py` global handler calls `logging.getLogger("api.error").error(..., exc_info=True)` (via `traceback.format_exc()` embedded in message OR via real `exc_info`)
- **THEN** the traceback text appears in the dated loguru error log file (`logs/logistics_error_<date>.log`)
- **AND** the file size is non-zero after the request completes

#### Scenario: stdlib logger.exception with exc_info preserves traceback
- **WHEN** any module calls `logging.getLogger(__name__).exception("msg")` inside an `except` block
- **THEN** the loguru file sink contains both the message and the full traceback

#### Scenario: Bridge does not duplicate loguru's own output
- **WHEN** loguru itself emits a log record via `from loguru import logger; logger.info(...)`
- **THEN** the record appears exactly once in each configured sink (no double-print from the bridge)

