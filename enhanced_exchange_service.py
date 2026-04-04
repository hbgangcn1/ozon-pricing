# -*- coding: utf-8 -*-
"""
增强汇率服务
解决汇率服务稳定性问题，提供多源汇率获取和本地存储
"""

import json
import os
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# 导入缓存服务
try:
    from redis_cache import (
        cache_exchange_rate,
        get_cached_exchange_rate,
        init_cache_system,
    )

    _cache_available = True
except ImportError:
    _cache_available = False
    cache_exchange_rate = None
    get_cached_exchange_rate = None
    init_cache_system = None

CACHE_AVAILABLE = _cache_available

# 导入数据库工具（用于动态 fallback）
try:
    from db_utils import get_exchange_rate_fallback, update_exchange_rate_fallback
except ImportError:
    # 兼容：db_utils 可能尚未加载
    def get_exchange_rate_fallback(currency_pair):
        return None

    def update_exchange_rate_fallback(currency_pair, rate, source=""):
        pass


# 尝试导入aiohttp用于异步请求（当前未使用，保留用于未来扩展）
try:
    import aiohttp  # pyright: ignore[reportUnusedImport]
    import asyncio  # pyright: ignore[reportUnusedImport]

    _aiohttp_available = True
except ImportError:
    _aiohttp_available = False
    aiohttp = None
    asyncio = None

AIOHTTP_AVAILABLE = _aiohttp_available

# 导入requests作为备用
try:
    import requests

    _requests_available = True
except ImportError:
    _requests_available = False
    requests = None

REQUESTS_AVAILABLE = _requests_available

# 配置日志
logging.basicConfig(level=logging.INFO)
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

    def __init__(self, provider_name: str, timeout: int = 10):
        self.name = provider_name
        self.timeout = timeout
        self.last_success_time = 0.0
        self.failure_count = 0
        self.max_failures = 3

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
            if not REQUESTS_AVAILABLE or requests is None:
                return None

            response = requests.get(self.url, timeout=self.timeout)
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
            if not REQUESTS_AVAILABLE or requests is None:
                return None

            response = requests.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            # 解析MOEX数据
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
            if not REQUESTS_AVAILABLE or requests is None:
                return None

            response = requests.get(self.url, timeout=self.timeout)
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
            if not REQUESTS_AVAILABLE or requests is None:
                return None

            response = requests.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if not data.get("success", False):
                error_info = data.get("error", {}).get("info", "Unknown error")
                raise ValueError(f"CurrencyLayer API错误: {error_info}")

            # CurrencyLayer返回的是RUBCNY，需要取倒数
            rate = 1.0 / float(data["quotes"]["RUBCNY"])
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
        except Exception:
            pass

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
            if not REQUESTS_AVAILABLE or requests is None:
                return None

            response = requests.get(self.url, timeout=self.timeout)
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
            if not REQUESTS_AVAILABLE or requests is None:
                return None

            response = requests.get(self.url, timeout=self.timeout)
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
            if not REQUESTS_AVAILABLE or requests is None:
                return None

            response = requests.get(self.url, timeout=self.timeout)
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
        except Exception:
            pass

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


class EnhancedExchangeRateService:
    """增强汇率服务"""

    def __init__(self, cache_ttl: int = 3600):
        self.cache_ttl = cache_ttl
        self.providers: List[ExchangeRateProvider] = []
        self.usd_providers: List[ExchangeRateProvider] = []
        self.local_storage_file = "enhanced_rate_storage.json"
        self.usd_local_storage_file = "enhanced_usd_rate_storage.json"
        self.lock = threading.Lock()

        self._init_providers()
        self._init_usd_providers()

        if CACHE_AVAILABLE and init_cache_system is not None:
            init_cache_system()

    def _init_providers(self):
        """初始化汇率提供者"""
        self.providers = [
            ExchangeRateAPIProvider(),
            MOEXProvider(),
            FixerIOProvider(),
            CurrencyLayerProvider(),
            LocalFallbackProvider(),
        ]

    def _init_usd_providers(self):
        """初始化USD汇率提供者"""
        self.usd_providers = [
            USDExchangeRateAPIProvider(),
            USDFixerIOProvider(),
            USDCurrencyLayerProvider(),
            USDLocalFallbackProvider(),
        ]

    def _save_to_local_storage(self, exchange_rate_data: ExchangeRateData):
        """保存到本地存储"""
        try:
            storage_data = {
                "rate": exchange_rate_data.rate,
                "timestamp": exchange_rate_data.timestamp,
                "source": exchange_rate_data.source.value,
                "currency_pair": exchange_rate_data.currency_pair,
                "confidence": exchange_rate_data.confidence,
                "saved_at": time.time(),
            }

            with open(self.local_storage_file, "w", encoding="utf-8") as f:
                json.dump(storage_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.warning(f"保存到本地存储失败: {e}")

    def _load_from_local_storage(self) -> Optional[ExchangeRateData]:
        """从本地存储加载"""
        try:
            if not os.path.exists(self.local_storage_file):
                return None

            with open(self.local_storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 检查数据是否过期
            if time.time() - data.get("saved_at", 0) > self.cache_ttl:
                return None

            return ExchangeRateData(
                source=ExchangeRateSource(data.get("source", "local_fallback")),
                rate=data.get("rate", 0.0904),
                timestamp=data.get("timestamp", time.time()),
                currency_pair=data.get("currency_pair", "RUB/CNY"),
                confidence=data.get("confidence", 0.5),
            )

        except Exception as e:
            logger.warning(f"从本地存储加载失败: {e}")
            return None

    @staticmethod
    def _get_best_rate(rates: List[ExchangeRateData]) -> ExchangeRateData:
        """选择最佳汇率"""
        if not rates:
            # 从数据库读取兜底汇率
            db_rate = get_exchange_rate_fallback("RUB_CNY")
            fallback_rate = round(db_rate, 4) if db_rate is not None else 0.0904
            return ExchangeRateData(
                source=ExchangeRateSource.LOCAL_FALLBACK,
                rate=fallback_rate,
                timestamp=time.time(),
                currency_pair="RUB/CNY",
                confidence=0.1,
                error_message="所有数据源都不可用",
            )

        # 按置信度和时间排序
        rates.sort(key=lambda x: (x.confidence, x.timestamp), reverse=True)
        # 如果最高置信度的汇率是兜底数据，尝试计算平均值
        if rates[0].source == ExchangeRateSource.LOCAL_FALLBACK and len(rates) > 1:
            # 计算非兜底数据的平均值
            non_fallback_rates = [
                r for r in rates if r.source != ExchangeRateSource.LOCAL_FALLBACK
            ]
            if non_fallback_rates:
                avg_rate = round(
                    sum(r.rate for r in non_fallback_rates) / len(non_fallback_rates), 4
                )
                return ExchangeRateData(
                    source=ExchangeRateSource.LOCAL_FALLBACK,
                    rate=avg_rate,
                    timestamp=time.time(),
                    currency_pair="RUB/CNY",
                    confidence=0.7,
                    error_message="使用多个数据源的平均值",
                )

        return rates[0]

    @staticmethod
    def _get_best_usd_rate(rates: List[ExchangeRateData]) -> ExchangeRateData:
        """选择最佳USD汇率"""
        if not rates:
            db_rate = get_exchange_rate_fallback("USD_CNY")
            fallback_rate = round(db_rate, 4) if db_rate is not None else 7.2
            return ExchangeRateData(
                source=ExchangeRateSource.LOCAL_FALLBACK_USD,
                rate=fallback_rate,
                timestamp=time.time(),
                currency_pair="USD/CNY",
                confidence=0.1,
                error_message="所有USD数据源都不可用",
            )

        rates.sort(key=lambda x: (x.confidence, x.timestamp), reverse=True)
        if rates[0].source == ExchangeRateSource.LOCAL_FALLBACK_USD and len(rates) > 1:
            non_fallback_rates = [
                r for r in rates if r.source != ExchangeRateSource.LOCAL_FALLBACK_USD
            ]
            if non_fallback_rates:
                avg_rate = round(
                    sum(r.rate for r in non_fallback_rates) / len(non_fallback_rates), 4
                )
                return ExchangeRateData(
                    source=ExchangeRateSource.LOCAL_FALLBACK_USD,
                    rate=avg_rate,
                    timestamp=time.time(),
                    currency_pair="USD/CNY",
                    confidence=0.7,
                    error_message="使用多个USD数据源的平均值",
                )

        return rates[0]

    def _save_usd_to_local_storage(self, exchange_rate_data: ExchangeRateData):
        """保存USD汇率到本地存储"""
        try:
            storage_data = {
                "rate": exchange_rate_data.rate,
                "timestamp": exchange_rate_data.timestamp,
                "source": exchange_rate_data.source.value,
                "currency_pair": exchange_rate_data.currency_pair,
                "confidence": exchange_rate_data.confidence,
                "saved_at": time.time(),
            }

            with open(self.usd_local_storage_file, "w", encoding="utf-8") as f:
                json.dump(storage_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.warning(f"保存USD到本地存储失败: {e}")

    def _load_usd_from_local_storage(self) -> Optional[ExchangeRateData]:
        """从本地存储加载USD汇率"""
        try:
            if not os.path.exists(self.usd_local_storage_file):
                return None

            with open(self.usd_local_storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if time.time() - data.get("saved_at", 0) > self.cache_ttl:
                return None

            return ExchangeRateData(
                source=ExchangeRateSource(data.get("source", "local_fallback_usd")),
                rate=data.get("rate", 7.2),
                timestamp=data.get("timestamp", time.time()),
                currency_pair=data.get("currency_pair", "USD/CNY"),
                confidence=data.get("confidence", 0.5),
            )

        except Exception as e:
            logger.warning(f"从本地存储加载USD失败: {e}")
            return None

    def get_exchange_rate(self, use_cache: bool = True) -> ExchangeRateData:
        """
        获取汇率

        Args:
            use_cache: 是否使用缓存

        Returns:
            ExchangeRateData: 汇率数据
        """
        with self.lock:
            # 尝试从缓存获取
            if use_cache and CACHE_AVAILABLE and get_cached_exchange_rate is not None:
                cached_rate = get_cached_exchange_rate()
                if cached_rate:
                    return ExchangeRateData(
                        source=ExchangeRateSource.LOCAL_FALLBACK,
                        rate=cached_rate,
                        timestamp=time.time(),
                        currency_pair="RUB/CNY",
                        confidence=0.8,
                        error_message="来自缓存",
                    )

            # 尝试从本地存储获取
            if use_cache:
                local_rate = self._load_from_local_storage()
                if local_rate:
                    return local_rate

            # 从多个数据源获取
            rates = []
            for provider in self.providers:
                if provider.is_available():
                    try:
                        provider_rate = provider.get_rate()
                        if provider_rate:
                            rates.append(provider_rate)
                            logger.info(
                                f"从 {provider.name} 获取汇率: {provider_rate.rate}"
                            )
                    except Exception as e:
                        logger.warning(f"{provider.name} 获取汇率异常: {e}")

            # 选择最佳汇率
            best_rate = EnhancedExchangeRateService._get_best_rate(rates)

            # 保存到缓存和本地存储
            if CACHE_AVAILABLE and cache_exchange_rate is not None:
                cache_exchange_rate(best_rate.rate, self.cache_ttl)

            self._save_to_local_storage(best_rate)

            # 同时写入数据库作为动态 fallback
            try:
                update_exchange_rate_fallback(
                    "RUB_CNY", round(best_rate.rate, 6), best_rate.source.value
                )
            except Exception as e:
                logger.warning(f"保存汇率到数据库失败: {e}")

            return best_rate

    def get_usd_rate(self, use_cache: bool = True) -> float:
        """
        获取USD汇率

        Args:
            use_cache: 是否使用缓存

        Returns:
            float: USD/CNY汇率
        """
        with self.lock:
            if use_cache:
                local_rate = self._load_usd_from_local_storage()
                if local_rate:
                    logger.info(f"USD汇率来自本地存储: {local_rate.rate}")
                    return local_rate.rate

            rates = []
            for provider in self.usd_providers:
                if provider.is_available():
                    try:
                        provider_rate = provider.get_rate()
                        if provider_rate:
                            rates.append(provider_rate)
                            logger.info(
                                f"从 {provider.name} 获取USD汇率: {provider_rate.rate}"
                            )
                    except Exception as e:
                        logger.warning(f"{provider.name} 获取USD汇率异常: {e}")

            best_rate = EnhancedExchangeRateService._get_best_usd_rate(rates)
            self._save_usd_to_local_storage(best_rate)

            # 同时写入数据库作为动态 fallback
            try:
                update_exchange_rate_fallback(
                    "USD_CNY", round(best_rate.rate, 6), best_rate.source.value
                )
            except Exception as e:
                logger.warning(f"保存USD汇率到数据库失败: {e}")

            logger.info(
                f"USD汇率最终结果: {best_rate.rate} (来源: {best_rate.source.value})"
            )
            return best_rate.rate

    def get_fallback_exchange_rate(self) -> float:
        """获取兜底汇率（兼容性方法），返回4位小数"""
        exchange_rate_data = self.get_exchange_rate(use_cache=True)
        return round(exchange_rate_data.rate, 4)

    def get_fallback_usd_rate(self) -> float:
        """获取兜底USD汇率（兼容性方法），返回4位小数"""
        return round(self.get_usd_rate(use_cache=True), 4)

    @staticmethod
    def update_fallback_rates(rub_cny: float, usd_cny: float):
        """手动更新兜底汇率"""
        try:
            fallback_data = {
                "RUB_CNY": rub_cny,
                "USD_CNY": usd_cny,
                "last_updated": time.time(),
                "sources": ["manual_update"],
            }

            with open("rate_fallback.json", "w", encoding="utf-8") as f:
                json.dump(fallback_data, f, ensure_ascii=False, indent=2)

            logger.info(f"兜底汇率已更新: RUB/CNY={rub_cny}, USD/CNY={usd_cny}")

        except Exception as e:
            logger.error(f"更新兜底汇率失败: {e}")

    def get_provider_status(self) -> Dict[str, Any]:
        """获取提供者状态"""
        provider_status = {}
        for provider in self.providers:
            provider_status[provider.name] = {
                "available": provider.is_available(),
                "failure_count": provider.failure_count,
                "last_success": provider.last_success_time,
                "last_success_human": (
                    datetime.fromtimestamp(provider.last_success_time).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if provider.last_success_time > 0
                    else "从未成功"
                ),
            }
        return provider_status

    def test_all_providers(self) -> Dict[str, Any]:
        """测试所有提供者"""
        results = {}
        for provider in self.providers:
            try:
                test_rate_data = provider.get_rate()
                results[provider.name] = {
                    "success": test_rate_data is not None,
                    "rate": test_rate_data.rate if test_rate_data else None,
                    "confidence": (
                        test_rate_data.confidence if test_rate_data else None
                    ),
                    "error": (test_rate_data.error_message if test_rate_data else None),
                }
            except Exception as e:
                results[provider.name] = {
                    "success": False,
                    "rate": None,
                    "confidence": None,
                    "error": str(e),
                }
        return results


# 全局服务实例
_enhanced_service: Optional[EnhancedExchangeRateService] = None


def get_enhanced_exchange_service() -> EnhancedExchangeRateService:
    """获取增强汇率服务实例"""
    global _enhanced_service
    if _enhanced_service is None:
        _enhanced_service = EnhancedExchangeRateService()
    return _enhanced_service


# 兼容性函数
def get_fallback_exchange_rate() -> float:
    """获取兜底汇率（兼容性函数）"""
    exchange_service = get_enhanced_exchange_service()
    return exchange_service.get_fallback_exchange_rate()


def get_fallback_usd_rate() -> float:
    """获取兜底USD汇率（兼容性函数）"""
    exchange_service = get_enhanced_exchange_service()
    return exchange_service.get_fallback_usd_rate()


def get_usd_rate() -> float:
    """获取USD汇率（兼容性函数）"""
    exchange_service = get_enhanced_exchange_service()
    return exchange_service.get_usd_rate()


if __name__ == "__main__":
    # 测试增强汇率服务
    print("测试增强汇率服务...")

    test_service = get_enhanced_exchange_service()

    # 测试获取汇率
    print("\n1. 获取汇率:")
    rate_data = test_service.get_exchange_rate()
    print(f"汇率: {rate_data.rate}")
    print(f"数据源: {rate_data.source.value}")
    print(f"置信度: {rate_data.confidence}")
    print(f"错误信息: {rate_data.error_message}")

    # 测试提供者状态
    print("\n2. 提供者状态:")
    status = test_service.get_provider_status()
    for name, info in status.items():
        print(f"{name}: 可用={info['available']}, 失败次数={info['failure_count']}")

    # 测试所有提供者
    print("\n3. 测试所有提供者:")
    test_results = test_service.test_all_providers()
    for name, result in test_results.items():
        print(f"{name}: 成功={result['success']}, 汇率={result['rate']}")
