# -*- coding: utf-8 -*-
"""
统一日志配置模块
使用 loguru 替代标准 logging
"""

import sys
from typing import Optional
from loguru import logger as _logger  # type: ignore
from pathlib import Path

# 导出 logger 供其他模块使用
logger = _logger


class SensitiveFormatter:
    """敏感信息格式化器"""
    
    @staticmethod
    def mask_password(password: str) -> str:
        """脱敏密码"""
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
        parts = email.split('@')
        if len(parts) == 2:
            name = parts[0]
            if len(name) > 2:
                return f"{name[0]}****{name[-1]}@{parts[1]}"
        return "****"


def configure_logger(
    app_name: str = "logistics",
    log_level: str = "INFO",
    enable_console: bool = True,
    enable_file: bool = True,
    log_dir: str = "logs"
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
    
    # 移除默认处理器
    logger.remove()
    
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # 日志格式
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # 控制台输出（开发环境）
    if enable_console:
        logger.add(
            sys.stdout,
            colorize=True,
            format=log_format,
            level="DEBUG",
            enqueue=True  # 异步写入，避免阻塞
        )
    
    # 文件输出（所有级别）
    if enable_file:
        logger.add(
            f"{log_dir}/{app_name}_{{time:YYYY-MM-DD}}.log",
            rotation="00:00",          # 每天午夜轮转
            retention="30 days",       # 保留30天
            compression="zip",         # 压缩旧日志
            encoding="utf-8",
            level=log_level,
            format=log_format,
            enqueue=True,
            backtrace=True,            # 显示完整堆栈
            diagnose=True              # 显示变量值（注意敏感信息）
        )
    
    # 错误日志单独文件
    if enable_file:
        logger.add(
            f"{log_dir}/{app_name}_error_{{time:YYYY-MM-DD}}.log",
            rotation="100 MB",         # 100MB轮转
            retention="90 days",       # 错误日志保留90天
            compression="zip",
            encoding="utf-8",
            level="ERROR",
            format=log_format,
            enqueue=True,
            backtrace=True,
            diagnose=True
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
        logger.exception(message)
    else:
        logger.error(message, **kwargs)


def log_warning(message: str, **kwargs):
    """记录警告日志"""
    logger.warning(message, **kwargs)


def log_debug(message: str, **kwargs):
    """记录调试日志"""
    logger.debug(message, **kwargs)


# 初始化日志系统
configure_logger(
    app_name="logistics",
    log_level="INFO",
    enable_console=True,
    enable_file=True
)

# 确保 logger 可被正确导入
__all__ = ['logger', 'configure_logger', 'SensitiveFormatter', 
           'log_info', 'log_error', 'log_warning', 'log_debug']

