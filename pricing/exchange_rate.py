"""Exchange rate service re-exports and get_usd_rate wrapper."""

try:
    from exchange_service import (
        ExchangeRateService,  # noqa: F401
        get_usd_rate,  # noqa: F401
    )
except ImportError:
    ExchangeRateService = None
    get_usd_rate = None

__all__ = ["ExchangeRateService", "get_usd_rate"]
