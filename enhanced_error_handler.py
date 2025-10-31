# -*- coding: utf-8 -*-
"""
增强错误处理模块
提供详细的错误分类、日志记录和用户友好的错误消息
"""

import traceback
import logging
import json
import sqlite3
import re
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
    def sanitize_log_message(message: str) -> str:
        """
        清理日志消息中的敏感信息

        增强功能：
        - 移除数据库结构信息（表名、列名）
        - 移除SQL语句中的敏感数据
        - 移除文件路径中的敏感信息

        Args:
            message: 原始日志消息

        Returns:
            清理后的安全日志消息
        """
        if not message:
            return message

        # 移除密码哈希（bcrypt格式: $2a$... 或 $2b$...）
        message = re.sub(
            r'\$2[ab]\$[0-9]{2}\$[A-Za-z0-9./]{53}',
            '[PASSWORD_HASH]',
            message
        )

        # 移除旧格式的SHA256哈希（64个十六进制字符）
        message = re.sub(
            r'\b[0-9a-f]{64}\b',
            '[HASH]',
            message
        )

        # 移除支付金额（amount=xxx 或 "amount": xxx）
        message = re.sub(
            r'(amount|price|total|value)["\']?\s*[:=]\s*\d+\.?\d*',
            r'\1=[REDACTED]',
            message,
            flags=re.IGNORECASE
        )

        # 移除信用卡号（16位数字，可能用空格或横线分隔）
        message = re.sub(
            r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            '[CARD_NUMBER]',
            message
        )

        # 移除数据库表名和列名（防止泄露数据库结构）
        # 匹配常见SQL语句中的表名和列名
        db_objects = [
            'users', 'products', 'logistics', 'payment_orders',
            'password', 'email', 'username', 'session_id',
            'user_id', 'order_id', 'transaction_id'
        ]
        for obj in db_objects:
            # 匹配表名和列名，但保留上下文信息
            message = re.sub(
                rf'\b{obj}\b',
                '[DB_OBJECT]',
                message,
                flags=re.IGNORECASE
            )

        # 移除SQL语句中的敏感数据（保留SQL结构但隐藏数据）
        # 匹配 SELECT ... FROM ... WHERE ... 模式
        sql_pattern = (
            r"(SELECT|INSERT|UPDATE|DELETE)\s+.*?\s+"
            r"(FROM|INTO|SET|WHERE)\s+(\w+).*?(\d+|'[^']*')"
        )
        message = re.sub(
            sql_pattern,
            r'\1 ... \2 [TABLE] ... [DATA]',
            message,
            flags=re.IGNORECASE | re.DOTALL
        )

        # 移除文件路径中的敏感信息（保留文件名但隐藏路径）
        message = re.sub(
            r'[A-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*([^\\/:*?"<>|\r\n]+)',
            r'[PATH]\1',
            message
        )
        message = re.sub(
            r'/(?:[^/]+/)*([^/]+)',
            r'[PATH]\1',
            message
        )

        # 移除邮箱地址（可选：如果不需要记录邮箱）
        # message = re.sub(
        #     r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        #     '[EMAIL]',
        #     message
        # )

        # 移除手机号（11位数字，中国手机号格式）
        message = re.sub(
            r'\b1[3-9]\d{9}\b',
            '[PHONE]',
            message
        )

        # 移除API密钥（通常包含大写字母、数字和连字符，长度20-40）
        message = re.sub(
            r'\b[A-Z0-9\-]{20,40}\b',
            '[API_KEY]',
            message
        )

        # 移除数据库文件路径（包含.db、.sqlite等）
        message = re.sub(
            r'[/\\][\w\s.\-]+\.(db|sqlite|sqlite3)',
            '[DB_PATH]',
            message,
            flags=re.IGNORECASE
        )

        # 移除绝对路径（Windows和Unix风格）
        message = re.sub(
            r'[C-Z]:\\\S+|/\S+',
            '[FILE_PATH]',
            message
        )

        # 移除微信支付相关敏感信息
        wechat_pattern = (
            r'(mch_id|app_id|api_v3_key|cert_serial_no)'
            r'["\']?\s*[:=]\s*["\']?[A-Za-z0-9]+["\']?'
        )
        message = re.sub(
            wechat_pattern,
            r'\1=[REDACTED]',
            message,
            flags=re.IGNORECASE
        )

        # 移除环境变量中的敏感值
        env_pattern = (
            r'(WECHAT_|DB_|REDIS_|SECRET_|KEY_|PASSWORD_|API_|TOKEN_)'
            r'[A-Z_]*["\']?\s*[:=]\s*["\']?[^\s"\']+["\']?'
        )
        message = re.sub(
            env_pattern,
            r'\1XXX=[REDACTED]',
            message,
            flags=re.IGNORECASE
        )

        # 移除数据库连接字符串中的敏感信息
        # 匹配格式: postgresql://user:password@host:port/dbname
        db_connection_pattern = (
            r'(postgresql|mysql|sqlite)://[^@]+@[^\s"\']+'
        )
        message = re.sub(
            db_connection_pattern,
            r'[DB_CONNECTION_REDACTED]',
            message,
            flags=re.IGNORECASE
        )

        # 移除JWT token（通常以eyJ开头）
        jwt_pattern = r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b'
        message = re.sub(jwt_pattern, '[JWT_TOKEN]', message)

        return message

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
        # 使用安全配置模块
        try:
            from .security_config import security_config
        except ImportError:
            from security_config import security_config

        # 检查是否为生产环境
        is_production = security_config.is_production()

        # 清理敏感信息后再添加到内存日志
        error_dict = error_info.to_dict()
        # 清理错误消息和traceback中的敏感信息
        error_dict['error_message'] = self.sanitize_log_message(
            error_dict['error_message']
        )
        error_dict['traceback'] = self.sanitize_log_message(
            error_dict['traceback']
        )

        # 生产环境下进一步清理：移除上下文中的敏感信息
        if is_production:
            # 移除用户ID、会话ID等敏感信息（保留类型但不保留值）
            if 'context' in error_dict:
                context = error_dict['context']
                if 'user_id' in context:
                    context['user_id'] = '[USER_ID]'
                if 'session_id' in context:
                    context['session_id'] = '[SESSION_ID]'
                if 'request_id' in context:
                    context['request_id'] = '[REQUEST_ID]'

        self.error_log.append(error_dict)

        # 保持日志大小限制
        if len(self.error_log) > self.max_log_size:
            self.error_log = self.error_log[-self.max_log_size:]

        # 记录到日志文件（已清理敏感信息）
        message = self.sanitize_log_message(error_info.message)
        severity = error_info.severity.value
        category = error_info.category.value

        # 生产环境下使用通用错误消息
        if is_production:
            log_message = (
                f"Error | Severity: {severity} | Category: {category}"
            )
        else:
            log_message = (
                f"Error: {message} | Severity: {severity} | "
                f"Category: {category}"
            )

        if error_info.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif error_info.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif error_info.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

    @staticmethod
    def get_user_friendly_message(
            error_info: ErrorInfo,
            show_details: bool = False) -> str:
        """
        获取用户友好的错误消息

        Args:
            error_info: 错误信息对象
            show_details: 是否显示详细错误信息（生产环境应为False）

        Returns:
            用户友好的错误消息
        """
        # 使用安全配置模块
        try:
            from .security_config import security_config
        except ImportError:
            from security_config import security_config

        # 检查是否为生产环境
        is_production = security_config.is_production()

        # 生产环境不显示详细错误信息，避免泄露数据库结构和技术细节
        if is_production and not show_details:
            category = error_info.category

            # 统一的生产环境错误消息，不泄露任何技术细节
            # 增强：不包含任何表名、列名、文件路径等敏感信息
            generic_messages = {
                ErrorCategory.DATABASE: "数据库操作失败，请稍后重试",
                ErrorCategory.NETWORK: "网络连接异常，请检查网络设置",
                ErrorCategory.VALIDATION: "输入数据格式不正确，请检查后重试",
                ErrorCategory.AUTHENTICATION: "身份验证失败，请重新登录",
                ErrorCategory.AUTHORIZATION: "权限不足，无法执行此操作",
                ErrorCategory.BUSINESS_LOGIC: "操作失败，请联系管理员",
                ErrorCategory.SYSTEM: "系统错误，请联系技术支持",
                ErrorCategory.UNKNOWN: "发生错误，请稍后重试"
            }

            return generic_messages.get(
                category, "发生错误，请稍后重试"
            )
        else:
            # 开发环境显示详细错误信息（但已脱敏）
            # 移除traceback中的敏感信息
            sanitized_message = ErrorHandler.sanitize_log_message(
                str(error_info.error)
            )

            # 进一步清理：移除可能的数据库结构信息
            # 移除常见的数据库错误信息中的表名和列名
            sanitized_message = re.sub(
                r"table\s+['\"]?(\w+)['\"]?\s+already exists",
                "table [TABLE_NAME] already exists",
                sanitized_message,
                flags=re.IGNORECASE
            )
            sanitized_message = re.sub(
                r"no such table:\s+(\w+)",
                "no such table: [TABLE_NAME]",
                sanitized_message,
                flags=re.IGNORECASE
            )
            sanitized_message = re.sub(
                r"no such column:\s+(\w+)",
                "no such column: [COLUMN_NAME]",
                sanitized_message,
                flags=re.IGNORECASE
            )

            return f"{sanitized_message}"

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
