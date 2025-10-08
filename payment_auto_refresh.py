"""
支付自动刷新组件
使用JavaScript实现前端轮询，避免阻塞Streamlit主线程
"""

import streamlit.components.v1 as components
import streamlit as st


def inject_simple_auto_refresh(check_interval_seconds: int = 3):
    """
    注入简单的自动刷新脚本
    每隔指定秒数自动刷新页面

    Args:
        check_interval_seconds: 刷新间隔（秒）
    """
    html_code = f"""
    <script>
    (function() {{
        const intervalSeconds = {check_interval_seconds};
        console.log("🔄 页面将在" + intervalSeconds + "秒后自动刷新");

        setTimeout(() => {{
            console.log("🔄 执行自动刷新");
            window.location.reload();
        }}, intervalSeconds * 1000);
    }})();
    </script>
    <div style="display:none;">Simple auto-refresh enabled</div>
    """

    components.html(html_code, height=0)


def show_auto_check_indicator(check_count: int = 0):
    """
    显示自动检查指示器

    Args:
        check_count: 当前检查次数
    """
    st.markdown(f"""
    <div style="
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 12px 20px;
        border-radius: 25px;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        font-size: 14px;
        font-weight: 500;
        z-index: 9999;
        animation: pulse 2s infinite;
    ">
        <span style="display: inline-block; margin-right: 8px;">🔄</span>
        自动检查中... (第 {check_count} 次)
    </div>
    <style>
        @keyframes pulse {{
            0%, 100% {{
                transform: scale(1);
                opacity: 1;
            }}
            50% {{
                transform: scale(1.05);
                opacity: 0.9;
            }}
        }}
    </style>
    """, unsafe_allow_html=True)
