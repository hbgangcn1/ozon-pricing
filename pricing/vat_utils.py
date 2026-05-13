from decimal import Decimal, InvalidOperation
from typing import Any


_ZERO = Decimal("0")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return _ZERO
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid VAT value: {value!r}") from exc


def normalize_vat_to_fraction(value: Any) -> Decimal:
    """Normalize any accepted VAT input to a Decimal fraction in [0, 1)."""
    # [PRC-W12R2-01]
    # Source of truth: models/product.py stores Product.vat_rate as Numeric(12, 4)
    # with default 0 and no DB-level percent/fraction constraint; existing fixtures and
    # API schemas allow both fractional values (Decimal("0.10")) and percent-form
    # values (20 / "20%", schema le=100). Consumers must normalize at calculation
    # boundaries without changing DB semantics.
    vat = _to_decimal(value)
    if vat < _ZERO:
        raise ValueError("VAT must be non-negative")
    if vat > _HUNDRED:
        raise ValueError("VAT percentage must be <= 100")
    if vat > _ONE:
        # [PRC-W12R2-01] Values above 1 are legacy/API percent form (20 => 20%).
        vat = vat / _HUNDRED
    if vat >= _ONE:
        raise ValueError("VAT fraction must be less than 1")
    return vat
