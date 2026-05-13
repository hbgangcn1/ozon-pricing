import json

from loguru import logger

import logger_config


class _Sink:
    def __init__(self):
        self.lines = []

    def write(self, message):
        self.lines.append(message)

    def flush(self):
        return None


def test_logger_json_format_contains_required_fields(monkeypatch, tmp_path):
    sink = _Sink()
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setattr(logger_config.sys, "stdout", sink)

    logger_config.configure_logger(
        app_name="test", enable_console=True, enable_file=False, log_dir=str(tmp_path)
    )
    logger.bind(request_id="req-1").info("hello")
    logger.complete()

    payload = json.loads(sink.lines[-1])
    record = payload["record"]
    assert payload["text"]
    assert record["time"]
    assert record["level"]["name"] == "INFO"
    assert record["message"] == "hello"
    assert record["module"] == "test_logger_json_format"
    assert record["function"] == "test_logger_json_format_contains_required_fields"
    assert isinstance(record["line"], int)
    assert record["process"]["id"]
    assert record["thread"]["id"]
    assert record["extra"]["request_id"] == "req-1"


def test_logger_text_format_is_not_json(monkeypatch, tmp_path):
    sink = _Sink()
    monkeypatch.setenv("LOG_FORMAT", "text")
    monkeypatch.setattr(logger_config.sys, "stdout", sink)

    logger_config.configure_logger(
        app_name="test", enable_console=True, enable_file=False, log_dir=str(tmp_path)
    )
    logger.info("plain text")
    logger.complete()

    try:
        json.loads("".join(sink.lines))
    except json.JSONDecodeError:
        return
    raise AssertionError("text log unexpectedly parsed as JSON")
