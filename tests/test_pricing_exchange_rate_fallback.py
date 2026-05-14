"""Test pricing/exchange_rate.py ImportError fallback."""
import sys
from unittest.mock import patch

import pytest


class TestExchangeRateImportFallback:
    def test_import_error_sets_none(self):
        """Cover except ImportError branch when enhanced_exchange_service is missing."""
        module_name = "enhanced_exchange_service"
        original = sys.modules.pop(module_name, None)
        try:
            if module_name in sys.modules:
                del sys.modules[module_name]

            with patch.dict(sys.modules, {module_name: None}):
                if "pricing.exchange_rate" in sys.modules:
                    del sys.modules["pricing.exchange_rate"]

                import pricing.exchange_rate as er_mod

                assert er_mod.ExchangeRateService is None
                assert er_mod.get_usd_rate is None
        finally:
            if original is not None:
                sys.modules[module_name] = original
            if "pricing.exchange_rate" in sys.modules:
                del sys.modules["pricing.exchange_rate"]
