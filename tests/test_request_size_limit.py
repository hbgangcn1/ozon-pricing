import pytest
from fastapi.testclient import TestClient

from api.main import app


# pyright: reportUnusedFunction=false


@app.post("/__w12_request_size_echo")
async def _echo_request_size():
    return {"ok": True}


def test_post_body_over_10mb_is_rejected_with_413():
    client = TestClient(app, raise_server_exceptions=False)
    oversized_body = b"x" * (11 * 1024 * 1024)

    response = client.post("/__w12_request_size_echo", content=oversized_body)

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body too large"}


def test_normal_size_post_body_passes():
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/__w12_request_size_echo", content=b"small")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
