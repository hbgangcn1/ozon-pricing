# -*- coding: utf-8 -*-
"""
安全配置管理模块
提供统一的环境变量管理和安全配置
"""

import os


class SecurityConfig:
    """安全配置类"""

    @staticmethod
    def is_production() -> bool:
        """检查是否为生产环境"""
        return (
            os.getenv('PRODUCTION_MODE', 'false').lower() == 'true' or
            os.getenv('ENVIRONMENT', '').lower() == 'production' or
            os.getenv('STREAMLIT_SERVER_ENV', '').lower() == 'production'
        )

    @staticmethod
    def is_development() -> bool:
        """检查是否为开发环境"""
        return not SecurityConfig.is_production()

    @staticmethod
    def get_log_level() -> str:
        """获取日志级别"""
        if SecurityConfig.is_production():
            return os.getenv('LOG_LEVEL', 'INFO').upper()
        else:
            return os.getenv('LOG_LEVEL', 'DEBUG').upper()

    @staticmethod
    def should_show_error_details() -> bool:
        """是否显示详细错误信息"""
        # 生产环境不显示详细错误信息
        return SecurityConfig.is_development()

    @staticmethod
    def should_sanitize_logs() -> bool:
        """是否对日志进行脱敏处理"""
        # 生产环境必须脱敏
        return SecurityConfig.is_production()

    @staticmethod
    def get_sensitive_env_vars() -> list:
        """获取敏感环境变量列表（用于脱敏）"""
        return [
            'WECHAT_APP_ID',
            'WECHAT_MCH_ID',
            'WECHAT_API_V3_KEY',
            'WECHAT_CERT_SERIAL_NO',
            'POSTGRES_PASSWORD',
            'DB_PASSWORD',
            'SECRET_KEY',
            'API_KEY',
            'TOKEN',
            'PASSWORD',
            'PASSWD',
            'REDIS_PASSWORD',
            'ACCESS_KEY',
            'SECRET_ACCESS_KEY'
        ]

    @staticmethod
    def sanitize_message(message: str) -> str:
        """脱敏消息中的敏感信息"""
        if not SecurityConfig.should_sanitize_logs():
            return message

        import re
        # 移除敏感环境变量的值
        for var in SecurityConfig.get_sensitive_env_vars():
            pattern = rf'{var}\s*[:=]\s*["\']?[^\s"\']+["\']?'
            message = re.sub(
                pattern,
                f'{var}=[REDACTED]',
                message,
                flags=re.IGNORECASE
            )

        return message


# 全局配置实例
security_config = SecurityConfig()
