"""Exchange rate service re-exports and get_usd_rate wrapper."""

try:
    from enhanced_exchange_service import (
        EnhancedExchangeRateService as ExchangeRateService,  # noqa: F401
        get_usd_rate,  # noqa: F401
    )
except ImportError:
    ExchangeRateService = None  # type: ignore[assignment]
    get_usd_rate = None  # type: ignore[assignment]

__all__ = ["ExchangeRateService", "get_usd_rate"]
