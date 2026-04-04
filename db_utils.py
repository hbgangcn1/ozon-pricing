"""Backward-compatibility shim — delegates everything to db/ package."""

import sys
import db as _db  # noqa: F401

sys.modules[__name__] = _db  # type: ignore[assignment]
sys.modules.setdefault("logistics.db_utils", _db)
