# -*- coding: utf-8 -*-
"""
CSRF保护模块（高优先级安全改进）
提供CSRF token生成和验证功能
"""

import secrets
import hashlib
import time
import streamlit as st
from typing import Optional


class CSRFProtection:
    """CSRF保护类（高优先级安全改进）"""

    CSRF_TOKEN_EXPIRY = 3600  # CSRF token有效期1小时
    CSRF_TOKEN_KEY = '_csrf_token'
    CSRF_TOKEN_TIME_KEY = '_csrf_token_time'

    @staticmethod
    def generate_csrf_token() -> str:
        """
        生成CSRF token

        Returns:
            CSRF token字符串
        """
        # 使用时间戳 + 随机数生成token
        timestamp = str(time.time())
        random_bytes = secrets.token_bytes(32)
        token_data = f"{timestamp}:{random_bytes.hex()}"
        return hashlib.sha256(token_data.encode()).hexdigest()

    @staticmethod
    def get_csrf_token() -> str:
        """
        获取或生成CSRF token（从session_state）

        Returns:
            CSRF token字符串
        """
        # 检查session_state中是否有token
        if CSRFProtection.CSRF_TOKEN_KEY not in st.session_state:
            # 生成新token
            token = CSRFProtection.generate_csrf_token()
            st.session_state[CSRFProtection.CSRF_TOKEN_KEY] = token
            st.session_state[CSRFProtection.CSRF_TOKEN_TIME_KEY] = time.time()
            return token

        # 检查token是否过期
        token_time = st.session_state.get(
            CSRFProtection.CSRF_TOKEN_TIME_KEY, 0
        )
        if time.time() - token_time > CSRFProtection.CSRF_TOKEN_EXPIRY:
            # Token过期，生成新token
            token = CSRFProtection.generate_csrf_token()
            st.session_state[CSRFProtection.CSRF_TOKEN_KEY] = token
            st.session_state[CSRFProtection.CSRF_TOKEN_TIME_KEY] = time.time()
            return token

        return st.session_state[CSRFProtection.CSRF_TOKEN_KEY]

    @staticmethod
    def validate_csrf_token(token: Optional[str]) -> tuple[bool, str]:
        """
        验证CSRF token

        Args:
            token: 要验证的token

        Returns:
            (is_valid, message): token是否有效，错误消息
        """
        if not token:
            return False, "CSRF token缺失"

        # 从session_state获取期望的token
        expected_token = st.session_state.get(CSRFProtection.CSRF_TOKEN_KEY)
        if not expected_token:
            return False, "CSRF token未初始化"

        # 检查token是否过期
        token_time = st.session_state.get(
            CSRFProtection.CSRF_TOKEN_TIME_KEY, 0
        )
        if time.time() - token_time > CSRFProtection.CSRF_TOKEN_EXPIRY:
            return False, "CSRF token已过期"

        # 比较token
        if token != expected_token:
            return False, "CSRF token不匹配"

        return True, ""

    @staticmethod
    def clear_csrf_token():
        """清除CSRF token（用于登出等场景）"""
        if CSRFProtection.CSRF_TOKEN_KEY in st.session_state:
            del st.session_state[CSRFProtection.CSRF_TOKEN_KEY]
        if CSRFProtection.CSRF_TOKEN_TIME_KEY in st.session_state:
            del st.session_state[CSRFProtection.CSRF_TOKEN_TIME_KEY]

    @staticmethod
    def refresh_csrf_token() -> str:
        """
        刷新CSRF token（生成新token）

        Returns:
            新的CSRF token
        """
        CSRFProtection.clear_csrf_token()
        return CSRFProtection.get_csrf_token()


# 便捷函数
def get_csrf_token() -> str:
    """获取CSRF token（便捷函数）"""
    return CSRFProtection.get_csrf_token()


def validate_csrf_token(token: Optional[str]) -> tuple[bool, str]:
    """验证CSRF token（便捷函数）"""
    return CSRFProtection.validate_csrf_token(token)
