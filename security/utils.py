# -*- coding: utf-8 -*-
"""
安全模块工具
提供客户端信息访问等工具函数
"""

from typing import Any

# Streamlit 上下文引用（供外部测试 monkeypatch）
# 不直接依赖 streamlit，调用方可替换此值
_streamlit: Any = None


def get_client_headers() -> dict:
    """获取当前请求头（从已注入的 _streamlit context 读取）"""
    if _streamlit is None:
        return {}
    try:
        if hasattr(_streamlit, "context") and hasattr(_streamlit.context, "headers"):
            headers = _streamlit.context.headers
            if headers:
                return dict(headers)
    except (AttributeError, TypeError):
        pass
    return {}
