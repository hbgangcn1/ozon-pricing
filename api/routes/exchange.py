from fastapi import APIRouter
from typing import Dict

from enhanced_exchange_service import (
    get_fallback_exchange_rate,
    get_fallback_usd_rate,
)

router = APIRouter(prefix="/api/exchange", tags=["汇率"])


@router.get("/rates", response_model=Dict[str, float])
def get_exchange_rates():
    """
    获取四种交叉汇率，精确到小数点后4位。
    返回：RUB/CNY, CNY/RUB, USD/CNY, CNY/USD
    """
    rub_cny = get_fallback_exchange_rate()
    cny_rub = 1.0 / rub_cny if rub_cny != 0 else 0.0
    usd_cny = get_fallback_usd_rate()
    cny_usd = 1.0 / usd_cny if usd_cny != 0 else 0.0

    # 四舍五入到4位小数
    rub_cny_rounded = round(rub_cny, 4)
    cny_rub_rounded = round(cny_rub, 4)
    usd_cny_rounded = round(usd_cny, 4)
    cny_usd_rounded = round(cny_usd, 4)

    return {
        "RUB/CNY": rub_cny_rounded,
        "CNY/RUB": cny_rub_rounded,
        "USD/CNY": usd_cny_rounded,
        "CNY/USD": cny_usd_rounded,
    }
