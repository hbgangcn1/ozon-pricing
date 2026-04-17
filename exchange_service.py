# Alias module for backward compatibility
# Maps to enhanced_exchange_service
from decimal import Decimal

from enhanced_exchange_service import *

# Provide fallback functions if not available
try:
    from enhanced_exchange_service import (
        get_fallback_exchange_rate,
        get_fallback_usd_rate,
    )
except ImportError:

    def get_fallback_exchange_rate():
        return Decimal("0.0904")

    def get_fallback_usd_rate():
        return Decimal("7.2")
