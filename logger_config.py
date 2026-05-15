# -*- coding: utf-8 -*-
"""
统一日志配置模块
使用 loguru 替代标准 logging
"""

import sys
import logging
import os
from typing import Optional
from pathlib import Path

# 尝试导入 loguru，如果失败则使用标准 logging
try:
    from loguru import logger as _logger  # type: ignore

    _loguru_available = True
except ImportError:
    # loguru 不可用，使用标准 logging 作为回退
    _loguru_available = False
    _logger = logging.getLogger("logistics")
    _logger.setLevel(logging.INFO)
    if not _logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        log_format = (
            "%(asctime)s | %(levelname)-8s | "
            "%(name)s:%(funcName)s:%(lineno)d | %(message)s"
        )
        handler.setFormatter(logging.Formatter(log_format))
        _logger.addHandler(handler)

# 导出 logger 供其他模块使用
logger = _logger

# 定义 LOGURU_AVAILABLE 常量
LOGURU_AVAILABLE = _loguru_available


class SensitiveFormatter:
    """敏感信息格式化器（高优先级安全改进：增强脱敏功能）"""

    @staticmethod
    def mask_password(_password: str) -> str:
        """脱敏密码 - 完全隐藏以保护安全"""
        return "****"

    @staticmethod
    def mask_card(card_number: str) -> str:
        """脱敏卡号"""
        if len(card_number) > 8:
            return f"{card_number[:4]}****{card_number[-4:]}"
        return "****"

    @staticmethod
    def mask_phone(phone: str) -> str:
        """脱敏手机号"""
        if len(phone) == 11:
            return f"{phone[:3]}****{phone[-4:]}"
        return "****"

    @staticmethod
    def mask_email(email: str) -> str:
        """脱敏邮箱"""
        parts = email.split("@")
        if len(parts) == 2:
            name = parts[0]
            if len(name) > 2:
                return f"{name[0]}****{name[-1]}@{parts[1]}"
        return "****"

    @staticmethod
    def mask_amount(amount: float) -> str:
        """脱敏支付金额（高优先级安全改进）"""
        # 只显示金额范围，不显示具体数值
        # 增强：金额转为分单位时的处理
        if amount < 100:
            return "小于100元"
        elif amount < 1000:
            return "100-1000元"
        elif amount < 10000:
            return "1000-10000元"
        else:
            return "大于10000元"

    @staticmethod
    def mask_payment_amount(amount_cents: int) -> str:
        """
        脱敏支付金额（分单位，高优先级安全改进）

        Args:
            amount_cents: 支付金额（分）

        Returns:
            str: 脱敏后的金额范围
        """
        amount_yuan = amount_cents / 100.0
        return SensitiveFormatter.mask_amount(amount_yuan)

    @staticmethod
    def mask_transaction_id(transaction_id: str) -> str:
        """脱敏交易号"""
        if not transaction_id or len(transaction_id) < 8:
            return "****"
        return f"{transaction_id[:4]}****{transaction_id[-4:]}"

    @staticmethod
    def mask_order_id(order_id: str) -> str:
        """脱敏订单号"""
        if not order_id or len(order_id) < 8:
            return "****"
        return f"{order_id[:4]}****{order_id[-4:]}"

    @staticmethod
    def mask_user_id(user_id: int) -> str:
        """脱敏用户ID（仅显示后4位）"""
        user_str = str(user_id)
        if len(user_str) <= 4:
            return "****"
        return f"****{user_str[-4:]}"

    @staticmethod
    def sanitize_message(message: str) -> str:
        """
        清理日志消息中的敏感信息（高优先级安全改进）

        自动检测并脱敏常见敏感信息模式
        """
        import re

        # 脱敏密码模式（password=xxx, pwd=xxx等）
        message = re.sub(
            r"(password|pwd|passwd)\s*[:=]\s*[^\s,;}\]]+",
            r"\1=****",
            message,
            flags=re.IGNORECASE,
        )

        # 脱敏数据库密码模式（POSTGRES_PASSWORD=xxx）
        message = re.sub(
            r"(POSTGRES_PASSWORD)\s*[:=]\s*[^\s,;}\]]+",
            r"\1=****",
            message,
            flags=re.IGNORECASE,
        )

        # 脱敏密钥模式（JWT_SECRET_KEY=xxx, SESSION_HMAC_SECRET=xxx）
        message = re.sub(
            r"(JWT_SECRET_KEY|SESSION_HMAC_SECRET)\s*[:=]\s*[^\s,;}\]]+",
            r"\1=****",
            message,
            flags=re.IGNORECASE,
        )

        # 脱敏微信支付密钥模式（WECHAT_API_V3_KEY=xxx）
        message = re.sub(
            r"(WECHAT_API_V3_KEY)\s*[:=]\s*[^\s,;}\]]+",
            r"\1=****",
            message,
            flags=re.IGNORECASE,
        )

        # 脱敏数据库连接 URL 中的密码（postgresql://user:password@host）
        message = re.sub(
            r"(postgresql://[^:]+):([^@]+)@",
            r"\1:****@",
            message,
            flags=re.IGNORECASE,
        )

        # 脱敏密钥在自然语言中的泄露（无 = 分隔的情况）
        # 例: "the jwt secret key is abcdef123", "session_hmac_secret is xyz"
        # Pattern 1: 下划线格式密钥名 + 连接器 + 值
        message = re.sub(
            r"(\b(?:jwt_secret_key|session_hmac_secret|wechat_api_v3_key|postgres_password))\s+(?:is|equals|=|:|为)\s+([A-Za-z0-9!@#$%^&*()_+=/-]+)",
            r"\1 ****",
            message,
            flags=re.IGNORECASE,
        )
        # Pattern 2: 空格分隔的自然语言 + 连接器 + 值
        message = re.sub(
            r"(\b(?:jwt secret key|session hmac secret|wechat api v3 key|postgres password))\s+(?:is|equals|=|:|为)\s+([A-Za-z0-9!@#$%^&*()_+=/-]+)",
            r"\1 ****",
            message,
            flags=re.IGNORECASE,
        )

        # 脱敏 Authorization Bearer token
        message = re.sub(
            r"(Authorization\s*[:=]\s*Bearer\s+)([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*|[A-Za-z0-9_-]+)",
            r"\1****",
            message,
            flags=re.IGNORECASE,
        )

        # 脱敏支付金额模式（金额=xxx, amount=xxx, 支付金额=xxx等）
        # 增强：匹配更多金额格式（包括分单位）
        amount_pattern = (
            r"(amount|金额|支付金额|金额为|"
            r"payment_amount|price|价格)\s*[:=]\s*[¥$]?\d+\.?\d*"
        )
        message = re.sub(
            amount_pattern, lambda m: f"{m.group(1)}=****", message, flags=re.IGNORECASE
        )

        # 脱敏交易号模式
        transaction_pattern = (
            r"(transaction_id|交易号|微信交易号|"
            r"wechat_transaction_id)\s*[:=]\s*([A-Z0-9]+)"
        )
        message = re.sub(
            transaction_pattern,
            lambda m: (
                f"{m.group(1)}={SensitiveFormatter.mask_transaction_id(m.group(2))}"
            ),
            message,
            flags=re.IGNORECASE,
        )

        # 脱敏支付回调相关数据
        message = re.sub(
            r"(out_trade_no|商户订单号|订单号)\s*[:=]\s*([A-Z0-9_]+)",
            lambda m: f"{m.group(1)}={SensitiveFormatter.mask_order_id(m.group(2))}",
            message,
            flags=re.IGNORECASE,
        )

        # 脱敏订单号模式
        message = re.sub(
            r"(order_id|订单号|订单ID)\s*[:=]\s*([A-Z0-9_]+)",
            lambda m: f"{m.group(1)}={SensitiveFormatter.mask_order_id(m.group(2))}",
            message,
            flags=re.IGNORECASE,
        )

        # 脱敏用户ID模式
        message = re.sub(
            r"(user_id|用户ID|用户id)\s*[:=]\s*(\d+)",
            lambda m: (
                f"{m.group(1)}={SensitiveFormatter.mask_user_id(int(m.group(2)))}"
            ),
            message,
            flags=re.IGNORECASE,
        )

        return message


class InterceptHandler(logging.Handler):
    """将 stdlib logging 路由到 loguru"""

    def emit(self, record: logging.LogRecord) -> None:
        from loguru import logger as _loguru

        try:
            level = _loguru.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        _loguru.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logger(
    app_name: str = "logistics",
    log_level: str = "INFO",
    enable_console: bool = True,
    enable_file: bool = True,
    log_dir: str = "logs",
):
    """
    配置全局日志器

    Args:
        app_name: 应用名称
        log_level: 日志级别
        enable_console: 是否输出到控制台
        enable_file: 是否输出到文件
        log_dir: 日志目录
    """
    if not LOGURU_AVAILABLE:
        # 如果 loguru 不可用，使用标准 logging 配置
        # 类型检查忽略：标准 logging.Logger 有 setLevel 方法
        if isinstance(logger, logging.Logger):
            logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        return

    # loguru 可用，使用 loguru 的配置
    # 类型检查忽略：loguru.Logger 有 remove 和 add 方法
    loguru_logger = logger  # type: ignore

    # 移除默认处理器
    loguru_logger.remove()  # type: ignore

    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # 日志格式（高优先级安全改进：自动脱敏敏感信息）
    def format_log(record):
        """自定义日志格式化函数，自动脱敏敏感信息"""
        message = str(record["message"])
        # 自动脱敏敏感信息
        message = SensitiveFormatter.sanitize_message(message)
        # 转义函数名中的特殊字符，防止loguru解析错误
        fn_name = record["function"].replace("<", "\\<").replace(">", "\\>")
        base = (
            f"<green>{record['time']:YYYY-MM-DD HH:mm:ss}</green> | "
            f"<level>{record['level'].name: <8}</level> | "
            f"<cyan>{record['name']}</cyan>:"
            f"<cyan>{fn_name}</cyan>:"
            f"<cyan>{record['line']}</cyan> | "
            f"<level>{message}</level>"
        )
        return base + "\n{exception}"

    serialize_logs = os.getenv("LOG_FORMAT", "text").lower() == "json"

    # 控制台输出（开发环境）
    if enable_console:
        kwargs = {
            "level": log_level,
            "enqueue": True,
            "serialize": serialize_logs,
        }
        if not serialize_logs:
            kwargs.update({"colorize": True, "format": format_log})
        loguru_logger.add(sys.stdout, **kwargs)  # type: ignore

    # 文件输出（所有级别）（高优先级安全改进：关闭diagnose避免泄露敏感信息）
    if enable_file:
        kwargs = {
            "rotation": "100 MB",
            "retention": "30 days",
            "compression": "zip",
            "encoding": "utf-8",
            "level": log_level,
            "enqueue": True,
            "backtrace": True,
            "diagnose": False,
            "serialize": serialize_logs,
        }
        if not serialize_logs:
            kwargs["format"] = format_log
        loguru_logger.add(  # type: ignore
            f"{log_dir}/{app_name}_{{time:YYYY-MM-DD}}.log", **kwargs
        )

    # 错误日志单独文件（高优先级安全改进：关闭diagnose避免泄露敏感信息）
    if enable_file:
        kwargs = {
            "rotation": "100 MB",
            "retention": "90 days",
            "compression": "zip",
            "encoding": "utf-8",
            "level": "ERROR",
            "enqueue": True,
            "backtrace": True,
            "diagnose": False,
            "serialize": serialize_logs,
        }
        if not serialize_logs:
            kwargs["format"] = format_log
        loguru_logger.add(  # type: ignore
            f"{log_dir}/{app_name}_error_{{time:YYYY-MM-DD}}.log", **kwargs
        )

    logger.info(f"日志系统初始化完成: {app_name}")
    logger.info(f"日志级别: {log_level}")
    logger.info(f"日志目录: {log_dir}")


# 全局日志器实例
def get_logger():
    """获取日志器实例"""
    return logger


# 便捷函数
def log_info(message: str, **kwargs):
    """记录信息日志"""
    logger.info(message, **kwargs)


def log_error(message: str, exception: Optional[Exception] = None, **kwargs):
    """记录错误日志"""
    if exception:
        if LOGURU_AVAILABLE:
            logger.exception(message)
        else:
            logger.error(message, exc_info=exception, **kwargs)
    else:
        logger.error(message, **kwargs)


def log_warning(message: str, **kwargs):
    """记录警告日志"""
    logger.warning(message, **kwargs)


def log_debug(message: str, **kwargs):
    """记录调试日志"""
    logger.debug(message, **kwargs)


# 初始化日志系统（仅在 loguru 可用时配置）
if LOGURU_AVAILABLE:
    configure_logger(
        app_name="logistics", log_level="INFO", enable_console=True, enable_file=True
    )
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
else:
    # loguru 不可用，使用标准 logging 的基本配置
    configure_logger(
        app_name="logistics",
        log_level="INFO",
        enable_console=True,
        enable_file=False,  # 标准 logging 需要额外配置才能写入文件
    )

# 确保 logger 可被正确导入
__all__ = [
    "logger",
    "configure_logger",
    "SensitiveFormatter",
    "log_info",
    "log_error",
    "log_warning",
    "log_debug",
    "log_safe_info",
    "log_safe_error",
    "log_safe_warning",
]


# 高优先级安全改进：便捷的脱敏日志函数
def log_safe_info(message: str, **kwargs):
    """记录信息日志（自动脱敏敏感信息）"""
    safe_message = SensitiveFormatter.sanitize_message(message)
    logger.info(safe_message, **kwargs)


def log_safe_error(message: str, exception: Optional[Exception] = None, **kwargs):
    """记录错误日志（自动脱敏敏感信息）"""
    safe_message = SensitiveFormatter.sanitize_message(message)
    if exception:
        if LOGURU_AVAILABLE:
            logger.exception(safe_message)
        else:
            logger.error(safe_message, exc_info=exception, **kwargs)
    else:
        logger.error(safe_message, **kwargs)


def log_safe_warning(message: str, **kwargs):
    """记录警告日志（自动脱敏敏感信息）"""
    safe_message = SensitiveFormatter.sanitize_message(message)
    logger.warning(safe_message, **kwargs)
