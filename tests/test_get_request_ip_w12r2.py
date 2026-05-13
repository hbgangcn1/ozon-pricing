from types import SimpleNamespace

# pyright: reportUnusedFunction=false

from starlette.datastructures import Headers


class _Request:
    def __init__(
        self,
        client_host: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.client = SimpleNamespace(host=client_host)
        self.headers = Headers(headers or {})


def _set_env(monkeypatch, *, trust: str, proxies: str):
    monkeypatch.setenv("TRUST_FORWARDED_FOR", trust)
    monkeypatch.setenv("TRUSTED_PROXY_IPS", proxies)
    import api.dependencies as dependencies

    return dependencies


def test_no_xff_trusted_disabled_returns_client_host(monkeypatch):
    dependencies = _set_env(
        monkeypatch,
        trust="false",
        proxies="127.0.0.1/32,::1/128",
    )

    request = _Request("198.51.100.10")

    assert dependencies.get_request_ip(request) == "198.51.100.10"


def test_xff_untrusted_client_returns_client_host(monkeypatch):
    dependencies = _set_env(
        monkeypatch,
        trust="true",
        proxies="127.0.0.1/32,::1/128",
    )

    request = _Request(
        "198.51.100.10",
        {"X-Forwarded-For": "203.0.113.5"},
    )

    assert dependencies.get_request_ip(request) == "198.51.100.10"


def test_xff_trusted_client_returns_leftmost_non_trusted_ip(monkeypatch):
    dependencies = _set_env(
        monkeypatch,
        trust="true",
        proxies="127.0.0.1/32,::1/128",
    )

    request = _Request(
        "127.0.0.1",
        {"X-Forwarded-For": "203.0.113.5"},
    )

    assert dependencies.get_request_ip(request) == "203.0.113.5"


def test_xff_multiple_proxies_returns_correct_origin(monkeypatch):
    dependencies = _set_env(
        monkeypatch,
        trust="true",
        proxies="127.0.0.1/32,10.0.0.0/8,::1/128",
    )

    request = _Request(
        "127.0.0.1",
        {"X-Forwarded-For": "198.51.100.7, 10.1.2.3, 10.4.5.6"},
    )

    assert dependencies.get_request_ip(request) == "198.51.100.7"


def test_malformed_xff_falls_back_to_client_host(monkeypatch):
    dependencies = _set_env(
        monkeypatch,
        trust="true",
        proxies="127.0.0.1/32,::1/128",
    )

    request = _Request(
        "127.0.0.1",
        {"X-Forwarded-For": "203.0.113.5, not-an-ip"},
    )

    assert dependencies.get_request_ip(request) == "127.0.0.1"


def test_ipv6_client_and_ipv6_trusted_cidr(monkeypatch):
    dependencies = _set_env(
        monkeypatch,
        trust="true",
        proxies="2001:db8:ffff::/48,::1/128",
    )

    request = _Request(
        "2001:db8:ffff::1",
        {"X-Forwarded-For": "2001:db8:1234::9, 2001:db8:ffff::2"},
    )

    assert dependencies.get_request_ip(request) == "2001:db8:1234::9"
