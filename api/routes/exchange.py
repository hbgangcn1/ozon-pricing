from decimal import Decimal, ROUND_HALF_UP
from typing import Dict

from fastapi import APIRouter

from enhanced_exchange_service import (
    get_fallback_exchange_rate,
    get_fallback_usd_rate,
)

router = APIRouter(prefix="/api/exchange", tags=["汇率"])

_Q4 = Decimal("0.0001")
_ONE = Decimal("1")
_ZERO = Decimal("0")


@router.get("/rates", response_model=Dict[str, float])
def get_exchange_rates():
    """
    获取四种交叉汇率，精确到小数点后4位。
    返回：RUB/CNY, CNY/RUB, USD/CNY, CNY/USD
    """
    rub_cny = get_fallback_exchange_rate()
    cny_rub = (
        (_ONE / rub_cny).quantize(_Q4, rounding=ROUND_HALF_UP)
        if rub_cny != _ZERO
        else _ZERO
    )
    usd_cny = get_fallback_usd_rate()
    cny_usd = (
        (_ONE / usd_cny).quantize(_Q4, rounding=ROUND_HALF_UP)
        if usd_cny != _ZERO
        else _ZERO
    )

    return {
        "RUB/CNY": float(rub_cny),
        "CNY/RUB": float(cny_rub),
        "USD/CNY": float(usd_cny),
        "CNY/USD": float(cny_usd),
    }
