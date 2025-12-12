import json
import os
import requests
import threading
import time
import asyncio
from abc import ABC, abstractmethod
from typing import Optional

# 导入streamlit用于缓存（当前未使用，保留用于未来扩展）
try:
    import streamlit as st  # pyright: ignore[reportUnusedImport]
except ImportError:
    # 如果streamlit不可用，定义占位装饰器
    def cache_data(ttl=None):
        # 使用ttl参数避免PyCharm警告，但在Mock实现中不需要实际使用
        _ = ttl  # 明确表示我们知道这个参数存在但不需要使用

        def decorator(func):
            return func
        return decorator

    class MockStreamlit:
        def __init__(self):
            self.cache_data = cache_data

    st = MockStreamlit()

# 异步HTTP客户端（可选依赖）
try:
    import aiohttp
    _aiohttp_available = True
except ImportError:
    _aiohttp_available = False
    aiohttp = None  # type: ignore

AIOHTTP_AVAILABLE = _aiohttp_available


try:
    from logger_config import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# ==================== 限流器配置 ====================
# 导入限流器
try:
    from rate_limiter import get_limiter
    _rate_limiter_available = True
except ImportError:
    _rate_limiter_available = False
    get_limiter = None  # type: ignore

RATE_LIMITER_AVAILABLE = _rate_limiter_available
# ===================================================


# ---------- 抽象接口
class ExchangeRateProvider(ABC):
    @abstractmethod
    def get_rate(self) -> float:
        pass


# ---------- 多源汇率提供者
class MultiSourceRubProvider(ExchangeRateProvider):
    """
    多数据源卢布汇率提供者，支持自动切换
    数据源优先级：
    1. exchangerate-api.com (主源)
    2. MOEX API (莫斯科交易所)
    3. fixer.io API (备用)
    """
    def __init__(self):
        self.sources = [
            {
                'name': 'ExchangeRate-API',
                'url': 'https://api.exchangerate-api.com/v4/latest/RUB',
                'parser': self._parse_exchangerate_api
            },
            {
                'name': 'MOEX',
                'url': (
                    'https://iss.moex.com/iss/statistics/engines/currency'
                    '/markets/selt/rates.json'
                ),
                'parser': self._parse_moex_api
            },
            {
                'name': 'ExchangeRates.io',
                'url': 'https://api.exchangerates.io/latest?base=RUB',
                'parser': self._parse_exchangerates_io
            },
            {
                'name': 'CurrencyLayer',
                'url': (
                    'https://api.currencylayer.com/live?access_key='
                    'YOUR_API_KEY&source=RUB&currencies=CNY'
                ),
                'parser': self._parse_currencylayer,
                'requires_key': True  # 需要API密钥
            },
        ]

    @staticmethod
    def _parse_exchangerate_api(data):
        """解析exchangerate-api.com的响应"""
        return float(data["rates"]["CNY"])

    @staticmethod
    def _parse_moex_api(data):
        """解析MOEX API的响应"""
        # MOEX返回USD/RUB，需要结合USD/CNY计算RUB/CNY
        # 简化实现：如果MOEX数据可用，使用其CNY/RUB比率
        if "statistics" in data and "data" in data["statistics"]:
            for item in data["statistics"]["data"]:
                if "CNYRUBTOM" in str(item):
                    return float(item[2])  # 汇率值
        raise ValueError("MOEX数据格式错误")

    @staticmethod
    def _parse_exchangerates_io(data):
        """解析ExchangeRates.io的响应"""
        if "rates" in data and "CNY" in data["rates"]:
            # ExchangeRates.io返回的是CNY/RUB（需要取倒数）
            cny_rate = float(data["rates"]["CNY"])
            if cny_rate > 0:
                return 1.0 / cny_rate
        raise ValueError("ExchangeRates.io数据格式错误")

    @staticmethod
    def _parse_currencylayer(data):
        """解析CurrencyLayer的响应"""
        # CurrencyLayer需要API密钥，如果没有配置则跳过
        if "quotes" in data and "RUBCNY" in data["quotes"]:
            return float(data["quotes"]["RUBCNY"])
        raise ValueError("CurrencyLayer数据格式错误或需要API密钥")

    @staticmethod
    async def _fetch_source_async(
        source: dict,
        timeout: int = 3
    ) -> Optional[float]:
        """异步获取单个数据源的汇率（静态方法）"""
        if not AIOHTTP_AVAILABLE:
            return None

        try:
            async with aiohttp.ClientSession() as session:  # type: ignore
                timeout_obj = aiohttp.ClientTimeout(  # type: ignore
                    total=timeout
                )
                async with session.get(
                    source['url'],
                    timeout=timeout_obj
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    rate = source['parser'](data)
                    logger.info(
                        f"异步汇率获取成功 - 来源: {source['name']}, "
                        f"汇率: {rate}"
                    )
                    return rate
        except Exception as e:
            logger.debug(f"{source['name']} 异步获取失败: {e}")
            return None

    async def get_rate_async(self) -> float:
        """
        异步并发获取汇率（优化版）
        同时请求所有数据源，返回最快响应的结果
        """
        if not AIOHTTP_AVAILABLE:
            # 降级到同步方法
            logger.warning("aiohttp 未安装，使用同步方法获取汇率")
            return self.get_rate_sync()

        # 限流检查
        if RATE_LIMITER_AVAILABLE and get_limiter:
            exchange_limiter = get_limiter(
                "exchange_rate_api", rate=30, per=60
            )
            limiter_key = "global_exchange_rate"

            if not exchange_limiter.is_allowed(limiter_key):
                retry_after = int(
                    exchange_limiter.get_retry_after(limiter_key)
                ) + 1
                logger.warning(
                    f"汇率API请求过于频繁，需等待 {retry_after} 秒"
                )
                raise ValueError(
                    f"汇率API限流中，请 {retry_after} 秒后重试"
                )

        # 并发请求所有数据源（跳过需要API密钥但未配置的数据源）
        tasks = []
        for source in self.sources:
            # 跳过需要API密钥但未配置的数据源
            if (source.get('requires_key') and
                    'YOUR_API_KEY' in source.get('url', '')):
                logger.debug(f"跳过需要API密钥的数据源: {source['name']}")
                continue
            tasks.append(
                asyncio.create_task(
                    MultiSourceRubProvider._fetch_source_async(source)
                )
            )

        try:
            # 使用 as_completed 获取第一个成功的结果
            for coro in asyncio.as_completed(tasks):
                try:
                    rate = await coro
                    if rate is not None:
                        # 成功获取汇率，取消并收尾剩余任务
                        for task in tasks:
                            if not task.done():
                                task.cancel()
                        # 等待所有任务完成取消，避免悬挂任务
                        try:
                            await asyncio.gather(
                                *tasks, return_exceptions=True
                            )
                        except asyncio.CancelledError:
                            # 忽略取消过程中的异常
                            pass
                        return rate
                except Exception as e:
                    logger.debug(f"并发获取汇率异常: {e}")
                    continue
        finally:
            # 确保所有任务被取消并完成收尾（即使抛出异常）
            for task in tasks:
                if not task.done():
                    task.cancel()
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                pass

        # 所有数据源都失败
        raise ValueError("所有汇率数据源失败（异步模式）")

    def get_rate_sync(self) -> float:
        """同步获取汇率（保持原有逻辑，作为兜底）"""
        # 限流检查：每分钟最多30次汇率请求
        if RATE_LIMITER_AVAILABLE and get_limiter:
            exchange_limiter = get_limiter(
                "exchange_rate_api", rate=30, per=60
            )
            limiter_key = "global_exchange_rate"

            if not exchange_limiter.is_allowed(limiter_key):
                retry_after = int(
                    exchange_limiter.get_retry_after(limiter_key)
                ) + 1
                logger.warning(
                    f"汇率API请求过于频繁，需等待 {retry_after} 秒"
                )
                raise ValueError(
                    f"汇率API限流中，请 {retry_after} 秒后重试"
                )

        last_error = None

        for source in self.sources:
            try:
                r = requests.get(source['url'], timeout=5)  # 缩短超时到5秒
                r.raise_for_status()
                data = r.json()
                rate = source['parser'](data)
                logger.info(
                    f"同步汇率获取成功 - 来源: {source['name']}, 汇率: {rate}"
                )
                # 记录成功，重置告警计数
                try:
                    from exchange_rate_alert import record_exchange_success
                    record_exchange_success()
                except ImportError:
                    pass
                return rate
            except Exception as e:
                logger.warning(f"{source['name']} 同步获取失败: {e}")
                last_error = e
                # 记录单个数据源失败
                try:
                    from exchange_rate_alert import record_exchange_failure
                    record_exchange_failure(str(e), source['name'])
                except ImportError:
                    pass
                continue

        # 所有数据源都失败
        raise ValueError(f"所有汇率数据源失败，最后错误: {last_error}")

    def get_rate(self) -> float:
        """
        获取汇率（智能选择同步/异步）
        优先使用异步方法，失败时降级到同步方法
        """
        if AIOHTTP_AVAILABLE:
            try:
                # 尝试获取或创建事件循环
                try:
                    # 尝试获取正在运行的事件循环
                    asyncio.get_running_loop()
                    # 如果事件循环正在运行，无法使用 run_until_complete
                    return self.get_rate_sync()
                except RuntimeError:
                    # 没有运行中的事件循环，创建新的并运行
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        return loop.run_until_complete(self.get_rate_async())
                    finally:
                        loop.close()
            except Exception as e:
                logger.warning(f"异步获取汇率失败，降级到同步: {e}")

        # 降级到同步方法
        return self.get_rate_sync()


# 保持向后兼容
class BocProvider(MultiSourceRubProvider):
    """向后兼容的别名"""
    pass


# ---------- 兜底实现：固定值
class FallbackProvider(ExchangeRateProvider):
    def __init__(self, default: float = 9.02):
        self.default = default

    def get_rate(self) -> float:
        return self.default


# ---------- 双缓存服务（单例，使用读写锁优化并发）
class ExchangeRateService:
    _instance = None
    _lock = threading.Lock()  # 用于单例创建的锁
    _fallback_file = os.path.join(
        os.path.dirname(__file__),
        "rate_fallback.json"
    )

    def __init__(self):
        # 仅为静态类型检查器提供属性初始化，避免"实例特性在 __init__ 外部定义"
        if not hasattr(self, "_rate"):
            self._provider = BocProvider()
            self._fallback = FallbackProvider()
            self._rate = 9.02
            self._last = 0.0
            self._refresher_started = False
            self._read_lock = threading.RLock()  # 读锁（可重入）
            self._write_lock = threading.Lock()  # 写锁

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
        return cls._instance

    def _init(self):
        self._provider = MultiSourceRubProvider()
        self._fallback = FallbackProvider()
        self._rate: float = 9.02
        self._last: float = 0
        # 初始化读写锁
        self._read_lock = threading.RLock()  # 读锁（可重入）
        self._write_lock = threading.Lock()  # 写锁
        self._load_fallback()
        self._start_async_refresh()

    @classmethod
    def _reset_for_testing(cls):
        """重置单例实例，仅用于测试"""
        with cls._lock:
            cls._instance = None

    def _reset_cache_for_testing(self):
        """重置缓存，仅用于测试"""
        self._last = 0.0
        self._rate = 9.02  # 重置为默认值

    def _load_fallback(self):
        """从本地文件加载兜底汇率（使用写锁）"""
        try:
            with open(self._fallback_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 写入汇率数据时使用写锁
            with self._write_lock:
                with self._read_lock:
                    self._rate = data["rate"]
                    self._last = data["ts"]
            logger.info(f"兜底汇率已加载: {self._rate:.5f}")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            with self._write_lock:
                with self._read_lock:
                    self._rate = self._fallback.get_rate()
                    self._last = time.time()
            logger.warning(f"兜底文件缺失，使用默认值: {self._rate:.5f}")

    def _save_fallback(self, rate: float):
        try:
            with open(self._fallback_file, "w", encoding="utf-8") as f:
                json.dump({"rate": rate, "ts": time.time()}, f)
        except OSError:
            logger.exception("无法保存兜底汇率")

    def _start_async_refresh(self):
        if not getattr(self, "_refresher_started", False):
            threading.Thread(target=self._async_refresh, daemon=True).start()
            self._refresher_started = True

    def _async_refresh(self):
        """异步刷新汇率（使用写锁）"""
        while True:
            try:
                # 使用优化后的获取方法（支持并发）
                new_rate = self._provider.get_rate()
                # 使用写锁更新汇率
                with self._write_lock:
                    with self._read_lock:
                        self._rate = new_rate
                        self._last = time.time()
                self._save_fallback(new_rate)
                logger.info(f"后台刷新汇率成功: {new_rate:.5f}")
            except (requests.RequestException, ValueError, Exception) as e:
                logger.warning(f"后台获取汇率失败，继续使用旧值: {e}")
            time.sleep(900)  # 15分钟（缩短缓存时间）

    def get_exchange_rate(self) -> float:
        """获取汇率（带缓存和读写锁优化）"""
        # 检查是否需要刷新（避免每次都发起网络请求）
        with self._read_lock:
            current_time = time.time()
            # 如果距离上次刷新不到60分钟，直接返回缓存值
            if current_time - self._last < 900:  # 15分钟缓存
                return self._rate

        # 需要刷新：获取写锁
        with self._write_lock:
            # 双重检查：可能其他线程已经刷新了
            with self._read_lock:
                if time.time() - self._last < 900:
                    return self._rate

            # 尝试即时刷新（支持并发请求）
            try:
                new_rate = self._provider.get_rate()
                # 更新时需要写锁保护
                with self._read_lock:
                    self._rate = new_rate
                    self._last = time.time()
                self._save_fallback(new_rate)
            except (requests.RequestException, ValueError, Exception):
                # 刷新失败，使用旧值
                pass

            with self._read_lock:
                return self._rate

    def get_cached_rate(self) -> float:
        """返回当前缓存的卢布兑人民币汇率，不触发刷新（只读操作）"""
        with self._read_lock:
            return self._rate


# ---------- 美元汇率提供者
class UsdProvider(ExchangeRateProvider):
    """
    使用 exchangerate-api.com 免费接口
    获取 1 USD → CNY 的实时汇率
    """
    def __init__(self):
        self.url = "https://api.exchangerate-api.com/v4/latest/USD"

    def get_rate(self) -> float:
        """获取美元汇率（带限流保护）"""
        # 限流检查：每分钟最多30次美元汇率请求
        if RATE_LIMITER_AVAILABLE and get_limiter:
            usd_limiter = get_limiter("usd_rate_api", rate=30, per=60)
            limiter_key = "global_usd_rate"

            if not usd_limiter.is_allowed(limiter_key):
                retry_after = int(
                    usd_limiter.get_retry_after(limiter_key)
                ) + 1
                logger.warning(
                    f"美元汇率API请求过于频繁，需等待 {retry_after} 秒"
                )
                raise ValueError(
                    f"美元汇率API限流中，请 {retry_after} 秒后重试"
                )

        try:
            r = requests.get(self.url, timeout=10)
            r.raise_for_status()
            data = r.json()
            # rates.CNY 即 1 USD 兑多少 CNY
            return float(data["rates"]["CNY"])
        except requests.RequestException as e:
            logger.warning(f"美元汇率接口失败: {e}")
        raise ValueError("第三方接口未返回美元汇率")


# ---------- 美元汇率服务
class UsdExchangeRateService:
    _instance = None
    _lock = threading.Lock()
    _fallback_file = os.path.join(
        os.path.dirname(__file__),
        "usd_rate_fallback.json"
    )

    def __init__(self):
        # 仅为静态类型检查器提供属性初始化，避免"实例特性在 __init__ 外部定义"
        if not hasattr(self, "_rate"):
            self._provider = UsdProvider()
            self._fallback = FallbackProvider(default=7.2)
            self._rate = 7.2
            self._last = 0.0
            self._refresher_started = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
        return cls._instance

    def _init(self):
        self._provider = UsdProvider()
        self._fallback = FallbackProvider(default=7.2)  # 美元默认汇率
        self._rate: float = 7.2
        self._last: float = 0
        self._load_fallback()
        self._start_async_refresh()

    @classmethod
    def _reset_for_testing(cls):
        """重置单例实例，仅用于测试"""
        with cls._lock:
            cls._instance = None

    def _reset_cache_for_testing(self):
        """重置缓存，仅用于测试"""
        self._last = 0.0
        self._rate = 7.2  # 重置为默认值

    def _load_fallback(self):
        try:
            with open(self._fallback_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._rate = data["rate"]
            self._last = data["ts"]
            logger.info(f"美元兜底汇率已加载: {self._rate:.5f}")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            self._rate = self._fallback.get_rate()
            self._last = time.time()
            logger.warning(f"美元兜底文件缺失，使用默认值: {self._rate:.5f}")

    def _save_fallback(self, rate: float):
        try:
            with open(self._fallback_file, "w", encoding="utf-8") as f:
                json.dump({"rate": rate, "ts": time.time()}, f)
        except OSError:
            logger.exception("无法保存美元兜底汇率")

    def _start_async_refresh(self):
        if not getattr(self, "_refresher_started", False):
            threading.Thread(target=self._async_refresh, daemon=True).start()
            self._refresher_started = True

    def _async_refresh(self):
        while True:
            try:
                new_rate = self._provider.get_rate()
                self._rate = new_rate
                self._last = time.time()
                self._save_fallback(new_rate)
                logger.info(f"异步刷新美元汇率: {new_rate:.5f}")
            except (requests.RequestException, ValueError):
                logger.exception("异步获取美元汇率失败，继续使用旧值")
            time.sleep(900)  # 15分钟（缩短缓存时间）

    def get_exchange_rate(self) -> float:
        # 检查是否需要刷新（避免每次都发起网络请求）
        current_time = time.time()
        # 如果距离上次刷新不到60分钟，直接返回缓存值
        if current_time - self._last < 3600:  # 60分钟缓存
            return self._rate

        try:
            new_rate = self._provider.get_rate()
            self._rate = new_rate
            self._last = current_time
            self._save_fallback(new_rate)
        except (requests.RequestException, ValueError):
            pass
        return self._rate

    def get_cached_rate(self) -> float:
        """返回当前缓存的美元兑人民币汇率，不触发刷新"""
        return self._rate


# ---------- 全局单例
def get_exchange_rate() -> float:
    return ExchangeRateService().get_exchange_rate()


# @st.cache_resource(ttl=3600)  # 缓存1小时，汇率变化不频繁 - 临时禁用
def get_usd_rate() -> float:
    """获取美元兑人民币汇率"""
    return UsdExchangeRateService().get_exchange_rate()


# ---------- 兜底汇率函数（不进行API调用）
def get_fallback_exchange_rate() -> float:
    """获取兜底汇率，不进行API调用，直接返回缓存值"""
    return ExchangeRateService().get_cached_rate()


def get_fallback_usd_rate() -> float:
    """获取美元兜底汇率，不进行API调用，直接返回缓存值"""
    return UsdExchangeRateService().get_cached_rate()
