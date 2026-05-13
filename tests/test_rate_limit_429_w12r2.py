from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.rate_limit import RateLimitMiddleware


def test_rate_limit_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setenv("PRODUCTION_MODE", "true")
    monkeypatch.setattr(
        "api.middleware.rate_limit._try_get_redis",
        lambda: None,
    )

    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=1,
        window_seconds=7,
    )

    @app.get("/limited")
    async def limited():
        return {"ok": True}

    client = TestClient(app)

    assert client.get("/limited").status_code == 200
    response = client.get("/limited")

    assert response.status_code == 429
    assert response.json() == {"detail": "请求过于频繁"}
    assert response.headers["Retry-After"].isdigit()
