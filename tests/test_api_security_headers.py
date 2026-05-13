import json

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from api.main import app, global_exception_handler


client = TestClient(app, raise_server_exceptions=False)


def test_docs_response_includes_security_headers():
    response = client.get("/docs")

    assert response.status_code == 200
    assert (
        response.headers["Strict-Transport-Security"]
        == "max-age=31536000; includeSubDomains"
    )
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_oversized_content_length_returns_413():
    response = client.post(
        "/",
        content=b"{}",
        headers={"Content-Length": str(10 * 1024 * 1024 + 1)},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large"}


@pytest.mark.asyncio
async def test_production_exception_response_masks_internal_detail(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/boom",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
        }
    )
    request.state.request_id = "req-test"

    response = await global_exception_handler(
        request,
        RuntimeError("secret stack trace detail"),
    )

    assert response.status_code == 500
    body = json.loads(response.body)
    assert body == {"detail": "Internal server error", "request_id": "req-test"}
    assert "secret" not in response.body.decode("utf-8")
