"""Async exchange-rate fetch helpers with single-flight cache miss protection."""

from __future__ import annotations

import asyncio
import os
import time
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Awaitable, Callable

import httpx

from enhanced_exchange_service import (
    CACHE_AVAILABLE,
    EnhancedExchangeRateService,
    ExchangeRateData,
    ExchangeRateSource,
    cache_exchange_rate,
    get_cached_exchange_rate,
    get_enhanced_exchange_service,
    update_exchange_rate_fallback,
)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_RETRY_DELAYS = (0.5, 1.0)
_Q4 = Decimal("0.0001")
_Q6 = Decimal("0.000001")
_client: httpx.AsyncClient | None = None
_locks: dict[str, asyncio.Lock] = {}


async def get_async_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=_TIMEOUT)
    return _client


async def close_async_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _request_json(url: str) -> dict[str, Any]:
    client = await get_async_client()
    last_exc: Exception | None = None
    for attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            response = await client.get(url)
            if response.status_code >= 500:
                response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt == len(_RETRY_DELAYS):
                raise
            await asyncio.sleep(_RETRY_DELAYS[attempt])
    raise RuntimeError("unreachable exchange retry state") from last_exc


async def _single_flight(
    key: str,
    cache_get: Callable[[], ExchangeRateData | Decimal | None],
    cache_set: Callable[[ExchangeRateData], None],
    fetcher: Callable[[], Awaitable[ExchangeRateData]],
) -> ExchangeRateData | Decimal:
    cached = cache_get()
    if cached is not None:
        return cached
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        cached = cache_get()
        if cached is not None:
            return cached
        value = await fetcher()
        cache_set(value)
        return value


def _cached_rub() -> ExchangeRateData | None:
    if CACHE_AVAILABLE and get_cached_exchange_rate is not None:
        cached = get_cached_exchange_rate()
        if cached:
            return ExchangeRateData(
                source=ExchangeRateSource.LOCAL_FALLBACK,
                rate=cached,
                timestamp=time.time(),
                currency_pair="RUB/CNY",
                confidence=0.8,
                error_message="来自缓存",
            )
    service: EnhancedExchangeRateService = get_enhanced_exchange_service()
    return service.get_cached_rate_data()


def _cache_rub(value: ExchangeRateData) -> None:
    service: EnhancedExchangeRateService = get_enhanced_exchange_service()
    if CACHE_AVAILABLE and cache_exchange_rate is not None:
        cache_exchange_rate(float(value.rate), service.cache_ttl)
    service.cache_rate_data(value)
    try:
        update_exchange_rate_fallback("RUB_CNY", round(value.rate, 6), value.source.value)
    except Exception:
        pass


def _cached_usd() -> ExchangeRateData | None:
    service: EnhancedExchangeRateService = get_enhanced_exchange_service()
    return service.get_cached_usd_rate_data()


def _cache_usd(value: ExchangeRateData) -> None:
    service: EnhancedExchangeRateService = get_enhanced_exchange_service()
    service.cache_usd_rate_data(value)
    try:
        update_exchange_rate_fallback("USD_CNY", round(value.rate, 6), value.source.value)
    except Exception:
        pass


def _best(rates: list[ExchangeRateData], pair: str) -> ExchangeRateData:
    if not rates:
        fallback = 0.0904 if pair == "RUB/CNY" else 7.2
        source = (
            ExchangeRateSource.LOCAL_FALLBACK
            if pair == "RUB/CNY"
            else ExchangeRateSource.LOCAL_FALLBACK_USD
        )
        return ExchangeRateData(source, fallback, time.time(), pair, 0.1, "所有数据源都不可用")
    rates.sort(key=lambda x: (x.confidence, x.timestamp), reverse=True)
    return rates[0]


async def _fetch_rub_rate() -> ExchangeRateData:
    rates: list[ExchangeRateData] = []
    try:
        data = await _request_json("https://api.exchangerate-api.com/v4/latest/RUB")
        rates.append(
            ExchangeRateData(
                ExchangeRateSource.EXCHANGERATE_API,
                float(data["rates"]["CNY"]),
                time.time(),
                "RUB/CNY",
                0.9,
            )
        )
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        pass
    try:
        data = await _request_json(
            "https://iss.moex.com/iss/statistics/engines/currency/"
            "markets/selt/rates.json"
        )
        for item in data.get("statistics", {}).get("data", []):
            if "CNYRUBTOM" in str(item):
                rates.append(
                    ExchangeRateData(
                        ExchangeRateSource.MOEX,
                        float(item[2]),
                        time.time(),
                        "RUB/CNY",
                        0.8,
                    )
                )
                break
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        pass
    return _best(rates, "RUB/CNY")


async def _fetch_usd_rate() -> ExchangeRateData:
    rates: list[ExchangeRateData] = []
    try:
        data = await _request_json("https://api.exchangerate-api.com/v4/latest/USD")
        rates.append(
            ExchangeRateData(
                ExchangeRateSource.EXCHANGERATE_API_USD,
                float(data["rates"]["CNY"]),
                time.time(),
                "USD/CNY",
                0.9,
            )
        )
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        pass
    api_key = os.getenv("CURRENCY_LAYER_API_KEY")
    if api_key:
        try:
            data = await _request_json(
                f"https://api.currencylayer.com/live?access_key={api_key}"
                "&currencies=CNY&source=USD"
            )
            if data.get("success", False):
                rates.append(
                    ExchangeRateData(
                        ExchangeRateSource.CURRENCY_LAYER_USD,
                        float(data["quotes"]["USDCNY"]),
                        time.time(),
                        "USD/CNY",
                        0.8,
                    )
                )
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            pass
    return _best(rates, "USD/CNY")


async def async_get_exchange_rate_data() -> ExchangeRateData:
    value = await _single_flight("exchange_rate:rub_cny", _cached_rub,
                                 _cache_rub, _fetch_rub_rate)
    return value if isinstance(value, ExchangeRateData) else _best([], "RUB/CNY")


async def async_get_fallback_exchange_rate() -> Decimal:
    data = await async_get_exchange_rate_data()
    return Decimal(str(data.rate)).quantize(_Q4, rounding=ROUND_HALF_UP)


async def async_get_fallback_usd_rate() -> Decimal:
    value = await _single_flight("exchange_rate:usd_cny", _cached_usd,
                                 _cache_usd, _fetch_usd_rate)
    rate = value.rate if isinstance(value, ExchangeRateData) else value
    return Decimal(str(rate)).quantize(_Q4, rounding=ROUND_HALF_UP)
