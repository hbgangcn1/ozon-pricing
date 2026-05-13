import asyncio
from decimal import Decimal

import httpx
import pytest

import exchange_async
from enhanced_exchange_service import ExchangeRateData, ExchangeRateSource


@pytest.fixture(autouse=True)
async def _reset_exchange_async_state(monkeypatch):
    exchange_async._locks.clear()
    exchange_async._client = None
    monkeypatch.setattr(exchange_async, "_RETRY_DELAYS", (0.01, 0.01))
    yield
    await exchange_async.close_async_client()
    exchange_async._locks.clear()


def _rate(value: float = 0.0912) -> ExchangeRateData:
    return ExchangeRateData(
        ExchangeRateSource.EXCHANGERATE_API,
        value,
        1.0,
        "RUB/CNY",
        0.9,
    )


async def test_single_flight_calls_fetcher_once_for_concurrent_miss():
    calls = 0
    cached: dict[str, ExchangeRateData | None] = {"value": None}

    def cache_get():
        return cached["value"]

    def cache_set(value):
        cached["value"] = value

    async def fetcher():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return _rate()

    results = await asyncio.gather(
        *[
            exchange_async._single_flight(
                "exchange_rate:rub_cny", cache_get, cache_set, fetcher
            )
            for _ in range(20)
        ]
    )

    assert calls == 1
    assert all(result is cached["value"] for result in results)


async def test_request_json_success_with_mock_transport():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"rates": {"CNY": 0.0912}})
    )
    exchange_async._client = httpx.AsyncClient(transport=transport)

    data = await exchange_async._request_json("https://example.test/rates")

    assert data == {"rates": {"CNY": 0.0912}}


async def test_request_json_retries_5xx_with_mock_transport():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503, json={"error": "busy"})
        return httpx.Response(200, json={"ok": True})

    exchange_async._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    data = await exchange_async._request_json("https://example.test/retry")

    assert data == {"ok": True}
    assert calls == 3


async def test_request_json_raises_after_timeout_retries():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("boom", request=request)

    exchange_async._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.ReadTimeout):
        await exchange_async._request_json("https://example.test/timeout")

    assert calls == 3


async def test_async_get_fallback_exchange_rate_uses_single_flight(monkeypatch):
    calls = 0
    cached: dict[str, ExchangeRateData | None] = {"value": None}

    monkeypatch.setattr(exchange_async, "_cached_rub", lambda: cached["value"])
    monkeypatch.setattr(exchange_async, "_cache_rub", lambda value: cached.update(value=value))

    async def fetcher():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return _rate(0.092345)

    monkeypatch.setattr(exchange_async, "_fetch_rub_rate", fetcher)

    results = await asyncio.gather(
        *[exchange_async.async_get_fallback_exchange_rate() for _ in range(20)]
    )

    assert calls == 1
    assert all(result == Decimal("0.0923") for result in results)
