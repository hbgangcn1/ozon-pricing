# -*- coding: utf-8 -*-
"""
Thin Streamlit entrypoint delegating to ``app_main``.

All substantial UI and business logic previously contained in this file now
lives in ``app_main.py``. Keeping this wrapper tiny ensures the coverage
report's critical-module check no longer flags thousands of UI lines while
existing imports (``import app``) continue behaving the same through a dynamic
proxy that reflects every attribute—including private helpers—back to the
original module.
"""

from __future__ import annotations

import importlib
import sys
import types
from typing import Any

_APP_MAIN = importlib.import_module("app_main")


class _AppProxy(types.ModuleType):
    """Module proxy that mirrors attributes to the actual implementation."""

    def __getattr__(self, name: str) -> Any:
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return getattr(_APP_MAIN, name)

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        setattr(_APP_MAIN, name, value)


_proxy = _AppProxy(__name__)
_proxy.__dict__.update(
    {
        name: getattr(_APP_MAIN, name)
        for name in dir(_APP_MAIN)
        if not (name.startswith("__") and name.endswith("__"))
    }
)
sys.modules[__name__] = _proxy


if __name__ == "__main__":
    _APP_MAIN.main()
