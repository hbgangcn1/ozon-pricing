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

# 从提供者模块导入并重新导出，保持向后兼容
from exchange_service_providers import (  # noqa: E402, F401
    ExchangeRateSource,
    ExchangeRateData,
    ExchangeRateProvider,
    ExchangeRateAPIProvider,
    MOEXProvider,
    FixerIOProvider,
    CurrencyLayerProvider,
    LocalFallbackProvider,
    USDExchangeRateAPIProvider,
    USDFixerIOProvider,
    USDCurrencyLayerProvider,
    USDLocalFallbackProvider,
)


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

        rates.sort(key=lambda x: (x.confidence, x.timestamp), reverse=True)
        if rates[0].source == ExchangeRateSource.LOCAL_FALLBACK and len(rates) > 1:
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
        """获取汇率"""
        with self.lock:
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

            if use_cache:
                local_rate = self._load_from_local_storage()
                if local_rate:
                    return local_rate

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

            best_rate = EnhancedExchangeRateService._get_best_rate(rates)

            if CACHE_AVAILABLE and cache_exchange_rate is not None:
                cache_exchange_rate(best_rate.rate, self.cache_ttl)

            self._save_to_local_storage(best_rate)

            try:
                update_exchange_rate_fallback(
                    "RUB_CNY", round(best_rate.rate, 6), best_rate.source.value
                )
            except Exception as e:
                logger.warning(f"保存汇率到数据库失败: {e}")

            return best_rate

    def get_usd_rate(self, use_cache: bool = True) -> float:
        """获取USD汇率"""
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
    print("测试增强汇率服务...")

    test_service = get_enhanced_exchange_service()

    print("\n1. 获取汇率:")
    rate_data = test_service.get_exchange_rate()
    print(f"汇率: {rate_data.rate}")
    print(f"数据源: {rate_data.source.value}")
    print(f"置信度: {rate_data.confidence}")
    print(f"错误信息: {rate_data.error_message}")

    print("\n2. 提供者状态:")
    status = test_service.get_provider_status()
    for name, info in status.items():
        print(f"{name}: 可用={info['available']}, 失败次数={info['failure_count']}")

    print("\n3. 测试所有提供者:")
    test_results = test_service.test_all_providers()
    for name, result in test_results.items():
        print(f"{name}: 成功={result['success']}, 汇率={result['rate']}")
