from decimal import Decimal

from enhanced_exchange_service import EnhancedExchangeRateService
from exchange_service_providers import ExchangeRateData, ExchangeRateSource


def _rate(source, rate, confidence=1.0, timestamp=1.0):
    return ExchangeRateData(
        source=source,
        rate=rate,
        timestamp=timestamp,
        currency_pair="RUB/CNY",
        confidence=confidence,
    )


def test_multi_source_average_returns_decimal_quantized_to_six_places():
    result = EnhancedExchangeRateService._get_best_rate(
        [
            _rate(ExchangeRateSource.LOCAL_FALLBACK, Decimal("6.4"), 0.9, 4.0),
            _rate(ExchangeRateSource.EXCHANGERATE_API, Decimal("6.5"), 0.8, 3.0),
            _rate(ExchangeRateSource.MOEX, Decimal("7.0"), 0.7, 2.0),
            _rate(ExchangeRateSource.FIXER_IO, Decimal("7.2"), 0.6, 1.0),
        ]
    )

    assert isinstance(result.rate, Decimal)
    assert result.rate == Decimal("6.900000")


def test_single_rate_returns_existing_rate():
    rate = _rate(ExchangeRateSource.EXCHANGERATE_API, Decimal("7.123456"))

    assert EnhancedExchangeRateService._get_best_rate([rate]) is rate


def test_empty_rate_list_returns_local_fallback_data(monkeypatch):
    monkeypatch.setattr(
        "enhanced_exchange_service.get_exchange_rate_fallback",
        lambda currency_pair: None,
    )

    result = EnhancedExchangeRateService._get_best_rate([])

    assert result.source == ExchangeRateSource.LOCAL_FALLBACK
    assert result.error_message == "所有数据源都不可用"
