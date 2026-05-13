import pytest
from fastapi.testclient import TestClient

from api.main import app


# pyright: reportUnusedFunction=false


@app.get("/__w12_exception_no_leak")
async def _raise_known_exception():
    raise RuntimeError("secret stack trace marker")


def _assert_masked_response(response):
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error"
    assert "request_id" in body and isinstance(body["request_id"], str)
    assert "secret stack trace marker" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


def test_production_exception_handler_masks_stack_trace(monkeypatch):
    monkeypatch.setattr("api.main._get_app_environment", lambda: "production")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/__w12_exception_no_leak")

    _assert_masked_response(response)


def test_testing_environment_also_masks_to_match_w1a_contract(monkeypatch):
    # [API-W12-14] W1-A removed the testing-only escape hatch; every env
    # masks unhandled exceptions to prevent accidental detail leaks.
    monkeypatch.setattr("api.main._get_app_environment", lambda: "testing")
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/__w12_exception_no_leak")

    _assert_masked_response(response)
