from decimal import Decimal
from typing import Optional

from ._constants import CONVERGENCE_THRESHOLD as _Q4  # noqa: F401


def select_commission_rate_from_category(
    category: dict,
    fulfillment_type: str,
    price_rub: Decimal,
) -> Optional[Decimal]:
    # Pure-compute helper. DB I/O moved to api/routes/_pricing_helpers.py to satisfy
    # the pricing/ purity guard (no DB imports allowed in pricing/).
    prefix = "rfbs" if fulfillment_type == "rfbs" else "fbp"
    if price_rub <= 1500:
        tier = "tier1"
    elif price_rub <= 5000:
        tier = "tier2"
    else:
        tier = "tier3"
    return category.get(f"{prefix}_{tier}_rate", Decimal("0"))
