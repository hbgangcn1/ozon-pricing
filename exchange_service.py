# Alias module for backward compatibility
# Maps to enhanced_exchange_service
from decimal import Decimal

from enhanced_exchange_service import *
from exchange_async import (
    async_get_fallback_exchange_rate,
    async_get_fallback_usd_rate,
)
from pricing._pricing_helpers import get_wx_pay_fallback_rate

# Provide fallback functions if not available
try:
    from enhanced_exchange_service import (
        get_fallback_exchange_rate,
        get_fallback_usd_rate,
    )
except ImportError:

    def get_fallback_exchange_rate():
        return get_wx_pay_fallback_rate()

    def get_fallback_usd_rate():
        return Decimal("7.2")
