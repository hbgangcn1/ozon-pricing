"""Tests for stdlib logging → loguru bridge (InterceptHandler)."""
import io
import logging
import time

from loguru import logger as loguru_logger

import logger_config  # noqa: F401


def test_stdlib_exception_appears_in_loguru_error_sink():
    """stdlib logger.exception(...) → loguru via InterceptHandler."""
    output = io.StringIO()
    handler_id = loguru_logger.add(output, level="ERROR", format="{message}")
    try:
        marker = f"intercept_test_marker_{int(time.time() * 1000)}"
        stdlib_logger = logging.getLogger("intercept_test")

        try:
            raise ValueError(f"intercept_payload_{marker}")
        except ValueError:
            stdlib_logger.exception(marker)

        loguru_logger.complete()
        content = output.getvalue()
    finally:
        loguru_logger.remove(handler_id)

    assert marker in content, f"Test marker '{marker}' missing from log"
    assert "Traceback" in content, "Traceback missing from log"
    assert "intercept_payload_" in content, "Exception message body missing from traceback"
