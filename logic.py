"""Backward-compatibility shim — delegates everything to pricing/ package."""

import sys
import pricing as _pkg  # noqa: F401

sys.modules[__name__] = _pkg  # type: ignore[assignment]
sys.modules.setdefault("logistics.logic", _pkg)
