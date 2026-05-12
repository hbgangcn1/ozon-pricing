from fastapi.responses import JSONResponse


def test_set_token_cookie_uses_dev_flags(monkeypatch):
    from api.routes.auth_support import set_token_cookie

    monkeypatch.setenv("ENV", "development")
    response = JSONResponse({"ok": True})

    set_token_cookie(response, "access", "refresh")

    cookie = response.headers["set-cookie"]
    assert "Domain=.cbprice.cn" not in cookie
    assert "Secure" not in cookie


def test_set_token_cookie_uses_production_domain_and_secure(monkeypatch):
    from api.routes.auth_support import set_token_cookie

    monkeypatch.setenv("ENV", "production")
    response = JSONResponse({"ok": True})

    set_token_cookie(response, "access", "refresh")

    cookie = response.headers["set-cookie"]
    assert "Domain=.cbprice.cn" in cookie
    assert "Secure" in cookie
