# -*- coding: utf-8 -*-
"""
增强错误处理模块
提供详细的错误分类、日志记录和用户友好的错误消息
"""

import traceback
import logging
import json
import sqlite3
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
from functools import wraps


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误类别"""
    DATABASE = "database"
    NETWORK = "network"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class ErrorContext:
    """错误上下文信息"""

    def __init__(self, user_id: Optional[str] = None,
                 session_id: Optional[str] = None,
                 request_id: Optional[str] = None,
                 module: Optional[str] = None,
                 function: Optional[str] = None):
        self.user_id = user_id
        self.session_id = session_id
        self.request_id = request_id
        self.module = module
        self.function = function
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'user_id': self.user_id,
            'session_id': self.session_id,
            'request_id': self.request_id,
            'module': self.module,
            'function': self.function,
            'timestamp': self.timestamp
        }


class ErrorInfo:
    """错误信息类"""

    def __init__(self, error: Exception, severity: ErrorSeverity,
                 category: ErrorCategory, context: ErrorContext,
                 message: Optional[str] = None):
        self.error = error
        self.severity = severity
        self.category = category
        self.context = context
        self.message = message or str(error)
        self.traceback = traceback.format_exc()
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'error_type': type(self.error).__name__,
            'error_message': self.message,
            'severity': self.severity.value,
            'category': self.category.value,
            'context': self.context.to_dict(),
            'traceback': self.traceback,
            'timestamp': self.timestamp
        }


class ErrorHandler:
    """错误处理器"""

    def __init__(self):
        self.error_log = []
        self.max_log_size = 1000
        self.logger = ErrorHandler._setup_logger()

    @staticmethod
    def _setup_logger() -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('enhanced_error_handler')
        logger.setLevel(logging.DEBUG)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    @staticmethod
    def classify_error(error: Exception) -> tuple[ErrorSeverity,
                                                  ErrorCategory]:
        """分类错误"""
        # 数据库错误
        if isinstance(error, (sqlite3.Error, ConnectionError)):
            return ErrorSeverity.HIGH, ErrorCategory.DATABASE

        # 网络错误
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorSeverity.MEDIUM, ErrorCategory.NETWORK

        # 验证错误
        if isinstance(error, (ValueError, TypeError)):
            return ErrorSeverity.MEDIUM, ErrorCategory.VALIDATION

        # 认证错误
        if isinstance(error, PermissionError):
            return ErrorSeverity.HIGH, ErrorCategory.AUTHENTICATION

        # 系统错误
        if isinstance(error, (OSError, MemoryError)):
            return ErrorSeverity.CRITICAL, ErrorCategory.SYSTEM

        # 默认分类
        return ErrorSeverity.MEDIUM, ErrorCategory.UNKNOWN

    def log_error(self, error_info: ErrorInfo):
        """记录错误"""
        # 添加到内存日志
        self.error_log.append(error_info.to_dict())

        # 保持日志大小限制
        if len(self.error_log) > self.max_log_size:
            self.error_log = self.error_log[-self.max_log_size:]

        # 记录到日志文件
        message = error_info.message
        severity = error_info.severity.value
        category = error_info.category.value
        log_message = f"Error: {message} | Severity: {severity} | " \
                      f"Category: {category}"

        if error_info.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif error_info.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

    @staticmethod
    def get_user_friendly_message(error_info: ErrorInfo) -> str:
        """获取用户友好的错误消息"""
        category = error_info.category

        if category == ErrorCategory.DATABASE:
            return "数据库连接出现问题，请稍后重试"
        elif category == ErrorCategory.NETWORK:
            return "网络连接异常，请检查网络设置"
        elif category == ErrorCategory.VALIDATION:
            return "输入数据格式不正确，请检查后重试"
        elif category == ErrorCategory.AUTHENTICATION:
            return "身份验证失败，请重新登录"
        elif category == ErrorCategory.AUTHORIZATION:
            return "权限不足，无法执行此操作"
        elif category == ErrorCategory.BUSINESS_LOGIC:
            return "业务逻辑错误，请联系管理员"
        elif category == ErrorCategory.SYSTEM:
            return "系统内部错误，请联系技术支持"
        else:
            return "发生未知错误，请稍后重试"

    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要"""
        if not self.error_log:
            return {'status': 'no_data'}

        total_errors = len(self.error_log)
        critical_errors = sum(1 for e in self.error_log
                              if e['severity'] == 'critical')
        warning_errors = sum(1 for e in self.error_log
                             if e['severity'] == 'high')

        # 按类别统计
        category_dist = {}
        for error in self.error_log:
            category = error['category']
            category_dist[category] = category_dist.get(category, 0) + 1

        # 按错误类型统计
        error_counts = {}
        for error in self.error_log:
            error_type = error['error_type']
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        # 今日错误
        today = datetime.now().date().isoformat()
        today_errors = sum(1 for e in self.error_log
                           if e['timestamp'].startswith(today))

        return {
            'status': 'success',
            'total_errors': total_errors,
            'critical_errors': critical_errors,
            'warning_errors': warning_errors,
            'today_errors': today_errors,
            'category_distribution': category_dist,
            'error_counts': error_counts,
            'recent_errors': self.error_log[-10:]  # 最近10个错误
        }

    def clear_error_log(self):
        """清空错误日志"""
        self.error_log = []


# 全局错误处理器实例
_error_handler = ErrorHandler()


def handle_error(severity: Optional[ErrorSeverity] = None,
                 category: Optional[ErrorCategory] = None,
                 user_message: Optional[str] = None,
                 context: Optional[ErrorContext] = None):
    """错误处理装饰器"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 创建错误上下文
                if context is None:
                    error_context = ErrorContext(
                        module=func.__module__,
                        function=func.__name__
                    )
                else:
                    error_context = context

                # 分类错误
                if severity is None or category is None:
                    auto_severity, auto_category = (
                        ErrorHandler.classify_error(e)
                    )
                    error_severity = severity or auto_severity
                    error_category = category or auto_category
                else:
                    error_severity = severity
                    error_category = category

                # 创建错误信息
                error_info = ErrorInfo(
                    error=e,
                    severity=error_severity,
                    category=error_category,
                    context=error_context,
                    message=user_message
                )

                # 记录错误
                _error_handler.log_error(error_info)

                # 返回用户友好的错误消息
                return ErrorHandler.get_user_friendly_message(error_info)

        return wrapper
    return decorator


def handle_database_error(func: Callable) -> Callable:
    """数据库错误处理装饰器"""
    return handle_error(
        severity=ErrorSeverity.HIGH,
        category=ErrorCategory.DATABASE
    )(func)


def handle_validation_error(func: Callable) -> Callable:
    """验证错误处理装饰器"""
    return handle_error(
        severity=ErrorSeverity.MEDIUM,
        category=ErrorCategory.VALIDATION
    )(func)


def handle_authentication_error(func: Callable) -> Callable:
    """认证错误处理装饰器"""
    return handle_error(
        severity=ErrorSeverity.HIGH,
        category=ErrorCategory.AUTHENTICATION
    )(func)


def safe_database_operation(operation_name: str = "数据库操作"):
    """安全数据库操作装饰器"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except sqlite3.Error as e:
                error_context = ErrorContext(
                    module=func.__module__,
                    function=func.__name__
                )
                error_info = ErrorInfo(
                    error=e,
                    severity=ErrorSeverity.HIGH,
                    category=ErrorCategory.DATABASE,
                    context=error_context,
                    message=f"{operation_name}失败: {str(e)}"
                )
                _error_handler.log_error(error_info)
                return None
            except Exception as e:
                error_context = ErrorContext(
                    module=func.__module__,
                    function=func.__name__
                )
                error_info = ErrorInfo(
                    error=e,
                    severity=ErrorSeverity.MEDIUM,
                    category=ErrorCategory.UNKNOWN,
                    context=error_context,
                    message=f"{operation_name}出现未知错误: {str(e)}"
                )
                _error_handler.log_error(error_info)
                return None

        return wrapper
    return decorator


def get_error_summary() -> Dict[str, Any]:
    """获取错误摘要"""
    return _error_handler.get_error_summary()


def clear_error_log():
    """清空错误日志"""
    _error_handler.clear_error_log()


def log_custom_error(error: Exception, severity: ErrorSeverity,
                     category: ErrorCategory,
                     context: Optional[ErrorContext] = None,
                     message: Optional[str] = None):
    """记录自定义错误"""
    if context is None:
        context = ErrorContext()

    error_info = ErrorInfo(
        error=error,
        severity=severity,
        category=category,
        context=context,
        message=message
    )

    _error_handler.log_error(error_info)


if __name__ == "__main__":
    # 测试错误处理功能
    @handle_database_error
    def test_database_operation():
        raise sqlite3.OperationalError("Database is locked")

    @handle_validation_error
    def test_validation_operation():
        raise ValueError("Invalid input data")

    # 测试错误处理
    print("测试数据库错误处理:")
    result = test_database_operation()
    print(f"结果: {result}")

    print("\n测试验证错误处理:")
    result = test_validation_operation()
    print(f"结果: {result}")

    # 获取错误摘要
    print("\n错误摘要:")
    summary = get_error_summary()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
