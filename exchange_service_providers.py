# -*- coding: utf-8 -*-
"""
汇率提供者模块
包含所有汇率数据源提供者类（基类、RUB/CNY 和 USD/CNY 系列）
"""

import json
import os
import threading
import time
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum

# 导入数据库工具（用于动态 fallback）
try:
    from db_utils import get_exchange_rate_fallback, update_exchange_rate_fallback
except ImportError:
    # 兼容：db_utils 可能尚未加载
    def get_exchange_rate_fallback(currency_pair):
        return None

    def update_exchange_rate_fallback(currency_pair, rate, source=""):
        pass


# 导入requests
try:
    import requests

    _requests_available = True
except ImportError:
    _requests_available = False
    requests = None

REQUESTS_AVAILABLE = _requests_available

logger = logging.getLogger(__name__)


class ExchangeRateSource(Enum):
    """汇率数据源枚举"""

    EXCHANGERATE_API = "exchangerate-api.com"
    EXCHANGERATE_API_USD = "exchangerate-api.com-usd"
    MOEX = "MOEX"
    FIXER_IO = "fixer.io"
    FIXER_IO_USD = "fixer.io-usd"
    CURRENCY_LAYER = "currencylayer.com"
    CURRENCY_LAYER_USD = "currencylayer.com-usd"
    EXCHANGE_RATES_IO = "exchangerates.io"
    LOCAL_FALLBACK = "local_fallback"
    LOCAL_FALLBACK_USD = "local_fallback-usd"


@dataclass
class ExchangeRateData:
    """汇率数据结构"""

    source: ExchangeRateSource
    rate: float
    timestamp: float
    currency_pair: str
    confidence: float = 1.0  # 置信度 0-1
    error_message: Optional[str] = None


class ExchangeRateProvider:
    """汇率提供者基类"""

    _shared_session: Optional[Any] = None
    _session_lock = threading.Lock()

    def __init__(self, provider_name: str, timeout: int = 10):
        self.name = provider_name
        self.timeout = timeout
        self.last_success_time = 0.0
        self.failure_count = 0
        self.max_failures = 3

    @classmethod
    def _get_session(cls):
        if not REQUESTS_AVAILABLE or requests is None:
            return None
        with cls._session_lock:
            if cls._shared_session is None:
                cls._shared_session = requests.Session()
                cls._shared_session.headers.update(
                    {
                        "Accept": "application/json",
                    }
                )
            return cls._shared_session

    @classmethod
    def close_shared_session(cls):
        with cls._session_lock:
            if cls._shared_session is not None:
                try:
                    cls._shared_session.close()
                except Exception:
                    pass
                cls._shared_session = None

    def is_available(self) -> bool:
        """检查数据源是否可用"""
        return self.failure_count < self.max_failures

    def get_rate(self) -> Optional[ExchangeRateData]:
        """获取汇率数据（子类实现）"""
        raise NotImplementedError

    def record_success(self):
        """记录成功"""
        self.last_success_time = time.time()
        self.failure_count = 0

    def record_failure(self, error: str):
        """记录失败"""
        self.failure_count += 1
        logger.warning(f"{self.name} 获取汇率失败: {error}")


class ExchangeRateAPIProvider(ExchangeRateProvider):
    """ExchangeRate-API提供者"""

    def __init__(self):
        super().__init__("ExchangeRate-API")
        self.url = "https://api.exchangerate-api.com/v4/latest/RUB"

    def get_rate(self) -> Optional[ExchangeRateData]:
        try:
            http = self._get_session()
            if http is None:
                return None

            response = http.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            rate = float(data["rates"]["CNY"])
            self.record_success()

            return ExchangeRateData(
                source=ExchangeRateSource.EXCHANGERATE_API,
                rate=rate,
                timestamp=time.time(),
                currency_pair="RUB/CNY",
                confidence=0.9,
            )

        except Exception as e:
            self.record_failure(str(e))
            return None


class MOEXProvider(ExchangeRateProvider):
    """MOEX提供者"""

    def __init__(self):
        super().__init__("MOEX")
        self.url = (
            "https://iss.moex.com/iss/statistics/engines/currency/"
            "markets/selt/rates.json"
        )

    def get_rate(self) -> Optional[ExchangeRateData]:
        try:
            http = self._get_session()
            if http is None:
                return None

            response = http.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if "statistics" in data and "data" in data["statistics"]:
                for item in data["statistics"]["data"]:
                    if "CNYRUBTOM" in str(item):
                        rate = float(item[2])
                        self.record_success()

                        return ExchangeRateData(
                            source=ExchangeRateSource.MOEX,
                            rate=rate,
                            timestamp=time.time(),
                            currency_pair="RUB/CNY",
                            confidence=0.8,
                        )

            raise ValueError("MOEX数据格式错误")
        except Exception as e:
            self.record_failure(str(e))
            return None


class FixerIOProvider(ExchangeRateProvider):
    """Fixer.io提供者"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("Fixer.io")
        self.api_key = api_key or os.getenv("FIXER_IO_API_KEY")
        self.url = (
            f"https://data.fixer.io/api/latest?access_key={self.api_key}"
            f"&base=RUB&symbols=CNY"
        )

    def get_rate(self) -> Optional[ExchangeRateData]:
        if not self.api_key:
            return None

        try:
            http = self._get_session()
            if http is None:
                return None

            response = http.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if not data.get("success", False):
                error_info = data.get("error", {}).get("info", "Unknown error")
                raise ValueError(f"Fixer.io API错误: {error_info}")

            rate = float(data["rates"]["CNY"])
            self.record_success()

            return ExchangeRateData(
                source=ExchangeRateSource.FIXER_IO,
                rate=rate,
                timestamp=time.time(),
                currency_pair="RUB/CNY",
                confidence=0.85,
            )

        except Exception as e:
            self.record_failure(str(e))
            return None


class CurrencyLayerProvider(ExchangeRateProvider):
    """CurrencyLayer提供者"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("CurrencyLayer")
        self.api_key = api_key or os.getenv("CURRENCY_LAYER_API_KEY")
        self.url = (
            f"https://api.currencylayer.com/live?access_key={self.api_key}"
            f"&currencies=CNY&source=RUB"
        )

    def get_rate(self) -> Optional[ExchangeRateData]:
        if not self.api_key:
            return None

        try:
            http = self._get_session()
            if http is None:
                return None

            response = http.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if not data.get("success", False):
                error_info = data.get("error", {}).get("info", "Unknown error")
                raise ValueError(f"CurrencyLayer API错误: {error_info}")

            rate = float(data["quotes"]["RUBCNY"])
            self.record_success()

            return ExchangeRateData(
                source=ExchangeRateSource.CURRENCY_LAYER,
                rate=rate,
                timestamp=time.time(),
                currency_pair="RUB/CNY",
                confidence=0.8,
            )

        except Exception as e:
            self.record_failure(str(e))
            return None


class LocalFallbackProvider(ExchangeRateProvider):
    """本地兜底提供者"""

    def __init__(self, fallback_file: str = "rate_fallback.json"):
        super().__init__("LocalFallback")
        self.fallback_file = fallback_file
        self.fallback_data = self._load_fallback_data()

    def _load_fallback_data(self) -> Dict[str, Any]:
        """从数据库读取兜底汇率，读不到时返回空字典触发API获取"""
        try:
            rate = get_exchange_rate_fallback("RUB_CNY")
            if rate is not None:
                return {
                    "RUB_CNY": round(rate, 6),
                    "last_updated": time.time(),
                    "sources": ["database"],
                }
        except Exception as e:
            logger.warning(f"从数据库加载RUB兜底汇率失败: {e}")

        # 尝试读旧的 JSON 文件作为过渡
        try:
            if os.path.exists(self.fallback_file):
                with open(self.fallback_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    rate = data.get("RUB_CNY")
                    if rate:
                        return data
        except (OSError, ValueError) as e:
            logger.warning("读取RUB兜底汇率JSON文件失败: %s", e)

        # 返回空字典，让系统走外部API，不要硬编码
        return {}

    def get_rate(self) -> Optional[ExchangeRateData]:
        try:
            rate = self.fallback_data.get("RUB_CNY")
            if rate is None:
                return None  # 没有有效汇率，让系统尝试其他数据源

            last_updated = self.fallback_data.get("last_updated", 0)

            # 如果数据太旧，降低置信度
            age_hours = (time.time() - last_updated) / 3600
            confidence = max(0.1, 1.0 - (age_hours / 24))  # 24小时后置信度为0.1

            return ExchangeRateData(
                source=ExchangeRateSource.LOCAL_FALLBACK,
                rate=rate,
                timestamp=last_updated,
                currency_pair="RUB/CNY",
                confidence=confidence,
                error_message=f"兜底数据，{age_hours:.1f}小时前更新",
            )

        except Exception as e:
            self.record_failure(str(e))
            return None


class USDExchangeRateAPIProvider(ExchangeRateProvider):
    """USD汇率 - ExchangeRate-API提供者"""

    def __init__(self):
        super().__init__("USD-ExchangeRate-API")
        self.url = "https://api.exchangerate-api.com/v4/latest/USD"

    def get_rate(self) -> Optional[ExchangeRateData]:
        try:
            http = self._get_session()
            if http is None:
                return None

            response = http.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            rate = float(data["rates"]["CNY"])
            self.record_success()

            return ExchangeRateData(
                source=ExchangeRateSource.EXCHANGERATE_API_USD,
                rate=rate,
                timestamp=time.time(),
                currency_pair="USD/CNY",
                confidence=0.9,
            )

        except Exception as e:
            self.record_failure(str(e))
            return None


class USDFixerIOProvider(ExchangeRateProvider):
    """USD汇率 - Fixer.io提供者"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("USD-Fixer.io")
        self.api_key = api_key or os.getenv("FIXER_IO_API_KEY")
        self.url = (
            f"https://data.fixer.io/api/latest?access_key={self.api_key}"
            f"&base=USD&symbols=CNY"
        )

    def get_rate(self) -> Optional[ExchangeRateData]:
        if not self.api_key:
            return None

        try:
            http = self._get_session()
            if http is None:
                return None

            response = http.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if not data.get("success", False):
                error_info = data.get("error", {}).get("info", "Unknown error")
                raise ValueError(f"Fixer.io USD API错误: {error_info}")

            rate = float(data["rates"]["CNY"])
            self.record_success()

            return ExchangeRateData(
                source=ExchangeRateSource.FIXER_IO_USD,
                rate=rate,
                timestamp=time.time(),
                currency_pair="USD/CNY",
                confidence=0.85,
            )

        except Exception as e:
            self.record_failure(str(e))
            return None


class USDCurrencyLayerProvider(ExchangeRateProvider):
    """USD汇率 - CurrencyLayer提供者"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("USD-CurrencyLayer")
        self.api_key = api_key or os.getenv("CURRENCY_LAYER_API_KEY")
        self.url = (
            f"https://api.currencylayer.com/live?access_key={self.api_key}"
            f"&currencies=CNY&source=USD"
        )

    def get_rate(self) -> Optional[ExchangeRateData]:
        if not self.api_key:
            return None

        try:
            http = self._get_session()
            if http is None:
                return None

            response = http.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if not data.get("success", False):
                error_info = data.get("error", {}).get("info", "Unknown error")
                raise ValueError(f"CurrencyLayer USD API错误: {error_info}")

            rate = float(data["quotes"]["USDCNY"])
            self.record_success()

            return ExchangeRateData(
                source=ExchangeRateSource.CURRENCY_LAYER_USD,
                rate=rate,
                timestamp=time.time(),
                currency_pair="USD/CNY",
                confidence=0.8,
            )

        except Exception as e:
            self.record_failure(str(e))
            return None


class USDLocalFallbackProvider(ExchangeRateProvider):
    """USD本地兜底提供者"""

    def __init__(self, fallback_file: str = "rate_fallback.json"):
        super().__init__("USD-LocalFallback")
        self.fallback_file = fallback_file
        self.fallback_data = self._load_fallback_data()

    def _load_fallback_data(self) -> Dict[str, Any]:
        """从数据库读取USD兜底汇率，读不到时返回空字典触发API获取"""
        try:
            rate = get_exchange_rate_fallback("USD_CNY")
            if rate is not None:
                return {
                    "USD_CNY": round(rate, 6),
                    "last_updated": time.time(),
                    "sources": ["database"],
                }
        except Exception as e:
            logger.warning(f"从数据库加载USD兜底汇率失败: {e}")

        # 尝试读旧的 JSON 文件作为过渡
        try:
            if os.path.exists(self.fallback_file):
                with open(self.fallback_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    rate = data.get("USD_CNY")
                    if rate:
                        return data
        except (OSError, ValueError) as e:
            logger.warning("读取USD兜底汇率JSON文件失败: %s", e)

        # 返回空字典，让系统走外部API，不要硬编码
        return {}

    def get_rate(self) -> Optional[ExchangeRateData]:
        try:
            rate = self.fallback_data.get("USD_CNY")
            if rate is None:
                return None  # 没有有效汇率，让系统尝试其他数据源
            last_updated = self.fallback_data.get("last_updated", 0)

            age_hours = (time.time() - last_updated) / 3600
            confidence = max(0.1, 1.0 - (age_hours / 24))

            return ExchangeRateData(
                source=ExchangeRateSource.LOCAL_FALLBACK_USD,
                rate=rate,
                timestamp=last_updated,
                currency_pair="USD/CNY",
                confidence=confidence,
                error_message=f"USD兜底数据，{age_hours:.1f}小时前更新",
            )

        except Exception as e:
            self.record_failure(str(e))
            return None
