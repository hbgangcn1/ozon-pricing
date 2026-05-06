"""Tests for stdlib logging → loguru bridge (InterceptHandler)."""
import logging
import time
from datetime import datetime
from pathlib import Path

from loguru import logger as loguru_logger

import logger_config  # noqa: F401


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _today_error_log() -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    return PROJECT_ROOT / "logs" / f"logistics_error_{today}.log"


def _flush_loguru() -> None:
    """Force loguru sinks to flush enqueued records."""
    try:
        loguru_logger.complete()
    except Exception:
        time.sleep(0.5)


def test_stdlib_exception_appears_in_loguru_error_sink():
    """stdlib logger.exception(...) → loguru error file with traceback."""
    log_file = _today_error_log()
    size_before = log_file.stat().st_size if log_file.exists() else 0

    marker = f"intercept_test_marker_{int(time.time() * 1000)}"
    stdlib_logger = logging.getLogger("intercept_test")

    try:
        raise ValueError(f"intercept_payload_{marker}")
    except ValueError:
        stdlib_logger.exception(marker)

    _flush_loguru()
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if log_file.exists() and log_file.stat().st_size > size_before:
            content_now = log_file.read_text(encoding="utf-8", errors="replace")
            if marker in content_now and "Traceback" in content_now:
                break
        time.sleep(0.1)

    assert log_file.exists(), f"Error log file not created: {log_file}"
    new_size = log_file.stat().st_size
    assert new_size > size_before, f"Error log did not grow: before={size_before} after={new_size}"
    content = log_file.read_text(encoding="utf-8", errors="replace")
    assert marker in content, f"Test marker '{marker}' missing from log"
    assert "Traceback" in content, "Traceback missing from log"
    assert "intercept_payload_" in content, "Exception message body missing from traceback"
